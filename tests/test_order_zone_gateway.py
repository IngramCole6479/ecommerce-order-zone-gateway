from src.order_zone_gateway import route_order


def test_order_stages_get_distinct_gateway_hosts():
    route = route_order("ORDER_1042", "shop.example")
    hosts = {route.checkout_host, route.fulfillment_host, route.receipt_host, route.updates_host}
    assert len(hosts) == 4
    assert route.checkout_host == "checkout-order-1042.shop.example"
