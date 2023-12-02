from decimal import Decimal
from store.models import Product, Collection, Review,Cart,CartItem,Customer,Order,OrderItem
from rest_framework import serializers
from django.db import transaction
from .signals import order_created
class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = ['id', 'title', 'products_count']

    products_count = serializers.IntegerField(read_only=True)


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'title', 'description', 'slug', 'inventory', 'unit_price', 'price_with_tax', 'collection']

    price_with_tax = serializers.SerializerMethodField(
        method_name='calculate_tax')

    def calculate_tax(self, product: Product):
        return product.unit_price * Decimal(1.1)

   
class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['id', 'date', 'name', 'description']

    def create(self, validated_data):
        product_id = self.context['product_id']
        return Review.objects.create(product_id=product_id, **validated_data)
    

class SimpleProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'title', 'unit_price']

class CartItemSerializer(serializers.ModelSerializer):
    product = SimpleProductSerializer()
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, cart_item: CartItem):
        return cart_item.quantity * cart_item.product.unit_price

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'total_price']


class CartSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, cart):
        return sum([item.quantity * item.product.unit_price for item in cart.items.all()])

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_price']
    
class AddCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['id','product_id','quantity']

    product_id = serializers.IntegerField()

    def validate_product_id(self,value):
        if not Product.objects.filter(pk = value).exists():
                raise serializers.ValidationError('no Product with the given ID')
        return value

    def save(self, **kwargs):
        cart_id = self.context['cart_id']
        product_id = self.validated_data['product_id']
        quantity = self.validated_data['quantity']
        try:
            cart_item = CartItem.objects.get(cart_id = cart_id,product_id =product_id)
            cart_item.quantity =+ quantity
            cart_item.save()
            cart_item = self.instance
        except CartItem.DoesNotExist:
            self.instance = CartItem.objects.create(cart_id =cart_id ,**self.validated_data)
        return self.instance

class UpdateCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['quantity']



class CustomerSerializer(serializers.ModelSerializer):

    user_id = serializers.IntegerField(read_only = True)

    class Meta:
        model = Customer
        fields = ['id','user_id','phone','birth_date','membership']


class OrderItemSerializer(serializers.ModelSerializer):

    product = SimpleProductSerializer()

    class Meta:
        model = OrderItem
        fields = ['id','product','unit_price','quantity']

class OrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id','customer','placed_at','payment_status','items']

class UpdateOrderSerializer(serializers.ModelSerializer):#creating this serializer because for patch operation only peyment status can change
    class Meta:
        model = Order
        fields = ['peyment_status']

class CreateOrderSerializer(serializers.Serializer):

    cart_id = serializers.UUIDField()  #we make a field in this serializer because for an order you should create a car first

    #validate the given cart id so that it wouldnt be false or empty
    def validate_cart_id(self,cart_id):      #syntax = validate_variable(self,variable)--->syntax of validating a field
        if not Cart.objects.filter(pk = cart_id).exists():
            raise serializers.ValidationError('No cart with the given ID was found.')
        if CartItem.objects.filter(cart_id = cart_id).count()==0:
            raise serializers.ValidationError('The cart is empty.')
        return cart_id  #Dont forget to return it..lol


    def save(self, **kwargs):
        with transaction.atomic(): #use transaction do undo changes if anything goes wrong we use it because we makelots changes in database)
            cart_id = self.validated_data['cart_id']    #we need cart_id and user_id to creat an order
            user_id = self.context['user_id']           #because the order is a cart that is transformed to order
            customer= Customer.objects.get(user_id = user_id)
            order = Order.objects.create(customer = customer)
            #after creating an order,for creating orderitems we pass this object to list_comprehension below

            #retreiving cartitem of the created cart to transform them into orderitems
            cart_item = CartItem.objects.select_related('product').\
                filter(cart_id = cart_id) 

            order_item = [OrderItem(          # transform cartitems into orderitems using list_comprehension
                            order = order,
                            product = item.product,
                            quantity = item.quantity,
                            unit_price = item.product.unit_price,
                            ) for item in cart_item]
            OrderItem.objects.bulk_create(order_item)     #save created orderitems with this syntax(less query)
            Cart.objects.filter(pk = cart_id).delete()    #then we delete the cart that was created for this order

            order_created.send_robust(self.__class__,order = order)

            return order #we return order so when the creation is complete we use this return to show the created order(we use in the views)