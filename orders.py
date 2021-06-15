from flask import Blueprint, request, jsonify
from google.cloud import datastore
import jwt_functions

client = datastore.Client()

bp = Blueprint('orders', __name__, url_prefix='/orders')
ORDERS = "orders"
ITEMS = "items"


# function to check for json request and authorization
def check_auth_accept(header):
    if (header['Accept'] != 'application/json') and (header['Accept'] != '*/*'):
        return jsonify({"Error": "Please make sure the accept is json."}), 406
    # if missing/invalid JWT return 401
    if 'Authorization' not in header:
        return jsonify({"Error": "Missing auth credentials."}), 401
    return None


# function to update an order entity
def update_order(entity, content, owner_id):
    entity.update({"has_shipped": content["has_shipped"],
                   "date": content["date"], "location": content["location"], "owner_id": owner_id})
    client.put(entity)
    result = client.get(entity.key)
    # set id and self
    result["id"] = entity.key.id
    result["self"] = request.url_root + 'orders/' + str(entity.key.id)
    return result


# create an order or get a list of all orders
@bp.route('', methods=['POST'])
def orders_post():
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    owner_id = payload["sub"]
    # creates an order for the user
    try:
        content = request.get_json()
        new_item = datastore.entity.Entity(key=client.key(ORDERS))
        result = update_order(new_item, content, owner_id)
        return jsonify(result), 201
    except KeyError:
        return jsonify({"Error": "The request object is missing at least one of the required attributes"}), 400


@bp.route('', methods=['GET'])
def orders_get():
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    query = client.query(kind=ORDERS)
    # NEED TO TEST THIS FILTER
    query.add_filter("owner_id", "=", payload["sub"])
    order_total = len(list(query.fetch()))
    q_limit = int(request.args.get('limit', '5'))
    q_offset = int(request.args.get('offset', '0'))
    l_iterator = query.fetch(limit=q_limit, offset=q_offset)
    pages = l_iterator.pages
    results = list(next(pages))
    if l_iterator.next_page_token:
        next_offset = q_offset + q_limit
        next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
    else:
        next_url = None
    for e in results:
        e["id"] = e.key.id
        e["self"] = request.url_root + 'orders/' + str(e.key.id)
        e["total_orders"] = order_total
    output = {"orders": results}
    if next_url:
        output["next"] = next_url
    return jsonify(output), 200


@bp.route('', methods=['PUT', 'DELETE'])
def orders_invalid():
    return jsonify({"Error": "These operations are not allowed on the entire list."}), 405


# grab a specific order or delete that specific order
@bp.route('/<id>', methods=['GET'])
def orders_get_specific(id):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    order_key = client.key(ORDERS, int(id))
    order = client.get(key=order_key)
    if not order:
        return jsonify({"Error": "No order with this order_id exists"}), 404
    if order["owner_id"] != payload["sub"]:
        return jsonify({"Error": "You are unauthorized to view this."}), 403
    order["id"] = order.key.id
    order["self"] = request.url_root + 'orders/' + str(order.key.id)
    return jsonify(order), 200


@bp.route('/<id>', methods=['PATCH'])
def orders_patch_specific(id):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    content = request.get_json()
    order_key = client.key(ORDERS, int(id))
    order = client.get(key=order_key)
    if not order:
        return jsonify({"Error": "No order with this order_id exists"}), 404
    if order["owner_id"] != payload["sub"]:
        return jsonify({"Error": "You are unauthorized to view this."}), 403
    for key in content:
        if order[key]:
            order[key] = content[key]
            client.put(order)
    order["id"] = order.key.id
    order["self"] = request.url_root + 'orders/' + str(order.key.id)
    return jsonify(order), 200


@bp.route('/<id>', methods=['PUT'])
def orders_put_specific(id):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    try:
        content = request.get_json()
        order_key = client.key(ORDERS, int(id))
        order = client.get(key=order_key)
        if not order:
            return jsonify({"Error": "No order with this order_id exists"}), 404
        if order["owner_id"] != payload["sub"]:
            return jsonify({"Error": "You are unauthorized to view this."}), 403
        owner_id = payload["sub"]
        result = update_order(order, content, owner_id)
        return jsonify(result), 200
    except KeyError:
        return jsonify({"Error": "The request object is missing at least one of the required attributes"}), 400


@bp.route('/<id>', methods=['DELETE'])
def orders_delete_specific(id):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    order_key = client.key(ORDERS, int(id))
    order = client.get(key=order_key)
    if not order:
        return jsonify({"Error": "No order with this order_id exists"}), 404
    if order["owner_id"] != payload["sub"]:
        return jsonify({"Error": "You are unauthorized to view this."}), 403
    # check if order has a item
    if 'items' in order.keys() and order['items'] is not None:
        for i in range(len(order['items'])):
            item_key = client.key(ITEMS, order['items'][i]['id'])
            item = client.get(key=item_key)
            # update item to not have that order
            i = 0
            length = len(item['orders'])
            while i < length:
                if order.key.id == item['orders'][i]['id']:
                    item['orders'].pop(i)
                    length = len(item['orders'])
                    client.put(item)
                else:
                    i += 1
    client.delete(order_key)
    return jsonify(''), 204


# put an item in an order or delete an item from an order
@bp.route('/<oid>/items/<iid>', methods=['PUT'])
def put_items_on_order(oid, iid):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    order_key = client.key(ORDERS, int(oid))
    order = client.get(key=order_key)
    item_key = client.key(ITEMS, int(iid))
    item = client.get(key=item_key)
    if not item or not order:
        return jsonify({"Error": "No order and/or item exists with this id."}), 404
    if order["owner_id"] != payload["sub"]:
        return jsonify({"Error": "You are unauthorized to view this."}), 403
    # check if item is already assigned to this order
    if 'items' in order.keys():
        for i in range(len(order['items'])):
            if item.key.id == order['items'][i]['id']:
                return jsonify({"Error": "This item is already on this order."}), 403
    # otherwise, assign the item to the order
    if 'items' in order.keys():
        order['items'].append({"id": item.key.id, "self": request.url_root + 'items/' + str(item.key.id)})
    else:
        order['items'] = [{"id": item.key.id, "self": request.url_root + 'items/' + str(item.key.id)}]
    client.put(order)
    item['orders'] = {"id": order.key.id, "self": request.url_root + 'orders/' + str(order.key.id)}
    client.put(item)
    return jsonify(''), 204


@bp.route('/<oid>/items/<iid>', methods=['DELETE'])
def delete_items_on_order(oid, iid):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    order_key = client.key(ORDERS, int(oid))
    order = client.get(key=order_key)
    item_key = client.key(ITEMS, int(iid))
    item = client.get(key=item_key)
    if not item or not order:
        return jsonify({"Error": "No order and/or item exists with this id."}), 404
    if order["owner_id"] != payload["sub"]:
        return jsonify({"Error": "You are unauthorized to view this."}), 403
    # check if item is actually on this order
    if 'items' in order.keys() and order['items'] is not None:
        i = 0
        length = len(order['items'])
        while i < length:
            if item.key.id == order['items'][i]['id']:
                order['items'].pop(i)
                length = len(order['items'])
                client.put(order)
                item['orders'] = None
                client.put(item)
                return '', 204
            else:
                i += 1
    return jsonify({"Error": "The item is not on this order."}), 404


# get all items for a given order
@bp.route('/<id>/items', methods=['GET'])
def items_get_specific(id):
    flag = check_auth_accept(request.headers)
    if flag:
        return flag
    payload = jwt_functions.verify_jwt(request)
    if not payload:
        return jsonify({"Error": "Unauthorized."}), 401
    order_key = client.key(ORDERS, int(id))
    order = client.get(key=order_key)
    if not order:
        return jsonify({"Error": "No order exists with this id."}), 404
    if order["owner_id"] != payload["sub"]:
        return jsonify({"Error": "You are unauthorized to view this."}), 403
    item_list = []
    if 'items' in order.keys() and order['items'] is not None:
        for i in range(len(order['items'])):
            item_key = client.key(ITEMS, order['items'][i]['id'])
            item = client.get(key=item_key)
            item["id"] = item.key.id
            item["self"] = request.url_root + 'items/' + str(item.key.id)
            item_list.append(item_key)
            client.put(item)
        return jsonify(client.get_multi(item_list)), 200
    else:
        return jsonify([]), 204
