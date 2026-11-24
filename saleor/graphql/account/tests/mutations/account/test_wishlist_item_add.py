import graphene

from ......account.models import User, WishlistItem
from ......product.models import ProductChannelListing
from .....tests.utils import assert_no_permission, get_graphql_content

WISHLIST_ITEM_ADD_MUTATION = """
mutation($variantId: ID!) {
  wishlistItemAdd(variantId: $variantId) {
    wishlistItem {
      id
      variant {
        id
      }
    }
    accountErrors {
      field
      code
    }
  }
}
"""


def _variant_id(variant):
    return graphene.Node.to_global_id("ProductVariant", variant.pk)


def test_wishlist_item_add_creates_item_for_current_customer(
    user_api_client, customer_user, variant
):
    # given
    variables = {"variantId": _variant_id(variant)}

    # when
    response = user_api_client.post_graphql(WISHLIST_ITEM_ADD_MUTATION, variables)

    # then
    data = get_graphql_content(response)["data"]["wishlistItemAdd"]
    assert not data["accountErrors"]
    assert data["wishlistItem"]["variant"]["id"] == _variant_id(variant)
    assert (
        WishlistItem.objects.filter(customer=customer_user, variant=variant).count()
        == 1
    )


def test_wishlist_item_add_twice_returns_existing_item(
    user_api_client, customer_user, variant
):
    # given
    variables = {"variantId": _variant_id(variant)}
    first = get_graphql_content(
        user_api_client.post_graphql(WISHLIST_ITEM_ADD_MUTATION, variables)
    )["data"]["wishlistItemAdd"]

    # when
    second = get_graphql_content(
        user_api_client.post_graphql(WISHLIST_ITEM_ADD_MUTATION, variables)
    )["data"]["wishlistItemAdd"]

    # then
    assert not second["accountErrors"]
    assert second["wishlistItem"]["id"] == first["wishlistItem"]["id"]
    assert (
        WishlistItem.objects.filter(customer=customer_user, variant=variant).count()
        == 1
    )


def test_wishlist_item_add_by_staff_saves_to_staff_own_wishlist(
    staff_api_client, customer_user, variant
):
    # given
    variables = {"variantId": _variant_id(variant)}

    # when
    response = staff_api_client.post_graphql(WISHLIST_ITEM_ADD_MUTATION, variables)

    # then
    data = get_graphql_content(response)["data"]["wishlistItemAdd"]
    assert not data["accountErrors"]
    assert not WishlistItem.objects.filter(customer=customer_user).exists()
    assert WishlistItem.objects.filter(
        customer=staff_api_client.user, variant=variant
    ).exists()


def test_wishlist_item_add_unknown_variant_returns_not_found(user_api_client):
    # given
    variables = {"variantId": graphene.Node.to_global_id("ProductVariant", 999999)}

    # when
    response = user_api_client.post_graphql(WISHLIST_ITEM_ADD_MUTATION, variables)

    # then
    data = get_graphql_content(response)["data"]["wishlistItemAdd"]
    assert data["wishlistItem"] is None
    assert data["accountErrors"][0]["field"] == "variantId"
    assert data["accountErrors"][0]["code"] == "NOT_FOUND"


def test_wishlist_item_add_anonymous_client_is_rejected(api_client, variant):
    # given
    variables = {"variantId": _variant_id(variant)}

    # when
    response = api_client.post_graphql(WISHLIST_ITEM_ADD_MUTATION, variables)

    # then
    assert_no_permission(response)
    assert not WishlistItem.objects.filter(variant=variant).exists()


def test_wishlist_item_add_does_not_touch_other_customers(user_api_client, variant):
    # given
    other_customer = User.objects.create(email="other-add@example.com")
    WishlistItem.objects.create(customer=other_customer, variant=variant)
    variables = {"variantId": _variant_id(variant)}

    # when
    user_api_client.post_graphql(WISHLIST_ITEM_ADD_MUTATION, variables)

    # then
    assert (
        WishlistItem.objects.filter(customer=other_customer, variant=variant).count()
        == 1
    )
    assert WishlistItem.objects.filter(customer=user_api_client.user).count() == 1


def test_wishlist_item_add_unpublished_variant_returns_not_found(
    user_api_client, variant
):
    # given
    ProductChannelListing.objects.filter(product=variant.product).update(
        is_published=False
    )
    variables = {"variantId": _variant_id(variant)}

    # when
    response = user_api_client.post_graphql(WISHLIST_ITEM_ADD_MUTATION, variables)

    # then
    data = get_graphql_content(response)["data"]["wishlistItemAdd"]
    assert data["wishlistItem"] is None
    assert data["accountErrors"][0]["code"] == "NOT_FOUND"
    assert not WishlistItem.objects.filter(variant=variant).exists()


def test_wishlist_item_add_variant_not_listed_in_channel_returns_not_found(
    user_api_client, variant
):
    # given
    ProductChannelListing.objects.filter(product=variant.product).delete()
    variables = {"variantId": _variant_id(variant)}

    # when
    response = user_api_client.post_graphql(WISHLIST_ITEM_ADD_MUTATION, variables)

    # then
    data = get_graphql_content(response)["data"]["wishlistItemAdd"]
    assert data["wishlistItem"] is None
    assert data["accountErrors"][0]["code"] == "NOT_FOUND"
    assert not WishlistItem.objects.filter(variant=variant).exists()
