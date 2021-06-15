from flask import Blueprint, request, jsonify
from google.cloud import datastore
import jwt_functions

client = datastore.Client()

bp = Blueprint('items', __name__, url_prefix='/items')
ITEMS = "items"
ORDERS = "orders"


# function to check for json request and authorization
def check_auth_accept(header):
    if (header['Accept'] != 'application/json') and (header['Accept'] != '*/*'):
        return jsonify({"Error": "Please make sure the accept is json."}), 406
    # if missing/invalid JWT return 401
    if 'Authorization' not in header:
        return jsonify({"Error": "Missing auth credentials."}), 401
    return None


# function to update a item entity
def update_item(entity, content, owner_id):
    entity.update({"item_name": content["item_name"], "quantity": content["quantity"],
                   "item_description": content["item_description"], "owner_id": owner_id})
    client.put(entity)
    result = client.get(entity.key)
    result["id"] = entity.key.id
    result["self"] = request.url_root + 'items/' + str(entity.key.id)
    return result


@bp.route('', methods=['POST'])
def items_post():
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    owner_id = payload["sub"]
    try:
        content = request.get_json()
        new_item = datastore.entity.Entity(key=client.key(ITEMS))
        result = update_item(new_item, content, owner_id)
        return jsonify(result), 201
    except KeyError:
        return jsonify({"Error": "The request object is missing at least one of the required attributes"}), 400


@bp.route('', methods=['GET'])
def items_get():
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    query = client.query(kind=ITEMS)
    query.add_filter("owner_id", "=", payload["sub"])
    item_total = len(list(query.fetch()))
    q_limit = int(request.args.get('limit', '5'))
    q_offset = int(request.args.get('offset', '0'))
    g_iterator = query.fetch(limit=q_limit, offset=q_offset)
    pages = g_iterator.pages
    results = list(next(pages))
    if g_iterator.next_page_token:
        next_offset = q_offset + q_limit
        next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
    else:
        next_url = None
    for e in results:
        e["id"] = e.key.id
        e["self"] = request.url_root + 'items/' + str(e.key.id)
        e["total_items"] = item_total
    output = {"items": results}
    if next_url:
        output["next"] = next_url
    return jsonify(output), 200


@bp.route('', methods=['PUT', 'DELETE'])
def items_invalid():
    # not allowed to put or delete on the entire list of entities
    return jsonify({"Error": "These operations are not allowed on the entire list."}), 405


# get a specified item's info
@bp.route('/<id>', methods=['GET'])
def items_get_specific(id):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    item_key = client.key(ITEMS, int(id))
    item = client.get(key=item_key)
    if not item:
        return jsonify({"Error": "No item with this item_id exists"}), 404
    if item["owner_id"] != payload["sub"]:
        return jsonify({"Error": "You are unauthorized to view this."}), 403
    item["id"] = item.key.id
    item["self"] = request.url_root + 'items/' + str(item.key.id)
    return jsonify(item)


@bp.route('/<id>', methods=['PATCH'])
def items_patch_specific(id):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    content = request.get_json()
    # make sure new requested name is not a duplicate
    item_key = client.key(ITEMS, int(id))
    item = client.get(key=item_key)
    if not item:
        return jsonify({"Error": "No item with this item_id exists"}), 404
    if item["owner_id"] != payload["sub"]:
        return jsonify({"Error": "You are unauthorized to view this."}), 403
    for key in content:
        if item[key]:
            item[key] = content[key]
            client.put(item)
    item["id"] = item.key.id
    item["self"] = request.url_root + 'items/' + str(item.key.id)
    return jsonify(item), 200


@bp.route('/<id>', methods=['PUT'])
def items_put_specific(id):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    try:
        content = request.get_json()
        item_key = client.key(ITEMS, int(id))
        item = client.get(key=item_key)
        if not item:
            return jsonify({"Error": "No item with this item_id exists"}), 404
        if item["owner_id"] != payload["sub"]:
            return jsonify({"Error": "You are unauthorized to view this."}), 403
        owner_id = payload["sub"]
        result = update_item(item, content, owner_id)
        return jsonify(result), 200
    except KeyError:
        return jsonify({"Error": "The request object is missing at least one of the required attributes"}), 400


@bp.route('/<id>', methods=['DELETE'])
def items_delete_specific(id):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    item_key = client.key(ITEMS, int(id))
    item = client.get(key=item_key)
    if not item:
        return jsonify({"Error": "No item with this item_id exists"}), 404
    if item["owner_id"] != payload["sub"]:
        return jsonify({"Error": "You are unauthorized to view this."}), 403
    # check if item is on a order and remove it
    if 'orders' in item.keys() and item['orders'] is not None:
        order_key = client.key(ORDERS, item['orders']['id'])
        order = client.get(key=order_key)
        # update order to remove this item
        if 'items' in order.keys() and order['items'] is not None:
            i = 0
            length = len(order['items'])
            while i < length:
                if item.key.id == order['items'][i]['id']:
                    order['items'].pop(i)
                    length = len(order['items'])
                    client.put(order)
                else:
                    i += 1
    client.delete(item_key)
    return jsonify(''), 204
