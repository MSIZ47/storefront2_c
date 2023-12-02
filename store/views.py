from store.pagination import DefaultPagination
from django.db.models.aggregates import Count
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from rest_framework.mixins import CreateModelMixin,RetrieveModelMixin,DestroyModelMixin,UpdateModelMixin
from rest_framework.viewsets import ModelViewSet,GenericViewSet
from rest_framework import status
from rest_framework.decorators import action,permission_classes
from .filters import ProductFilter
from .models import Collection, Product, Review,Cart,CartItem,Customer,Order,OrderItem
from .serializers import CollectionSerializer, ProductSerializer, ReviewSerializer,CartSerializer,CartItemSerializer,AddCartItemSerializer,UpdateCartItemSerializer,CustomerSerializer,OrderSerializer,CreateOrderSerializer,UpdateOrderSerializer
from rest_framework.permissions import IsAuthenticated,IsAdminUser

class ProductViewSet(ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    pagination_class = DefaultPagination
    search_fields = ['title', 'description']
    ordering_fields = ['unit_price', 'last_update']

    def get_serializer_context(self):
        return {'request': self.request}
    

    def destroy(self, request, *args, **kwargs):
        if OrderItem.objects.filter(product_id = kwargs['pk']).count()>0 :
            return Response({'error': 'Product cannot be deleted because it is associated with an order item.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return super().destroy(request, *args, **kwargs)

class CollectionViewSet(ModelViewSet):
    queryset = Collection.objects.annotate(
    products_count=Count('products')).all()
    serializer_class = CollectionSerializer


    def destroy(self, request, *args, **kwargs):
        if Product.objects.filter(collection_id = kwargs['pk']).count()>0 :
            return Response({'error': 'Collection cannot be deleted because it includes one or more products.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return super().destroy(request, *args, **kwargs)
    


class ReviewViewSet(ModelViewSet):
    serializer_class = ReviewSerializer

    def get_queryset(self):
        return Review.objects.filter(product_id=self.kwargs['product_pk'])

    def get_serializer_context(self):
        return {'product_id': self.kwargs['product_pk']}


class CartViewSet(CreateModelMixin,
                  RetrieveModelMixin,
                  DestroyModelMixin,
                  GenericViewSet):
    queryset = Cart.objects.prefetch_related('items__product').all()
    serializer_class = CartSerializer

class CartItemViewSet(ModelViewSet):

    http_method_names = ['post','get','patch','delete']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AddCartItemSerializer
        elif self.request.method == 'PATCH':
            return UpdateCartItemSerializer
        return CartItemSerializer

    def get_serializer_context(self):
        return {'cart_id': self.kwargs['cart_pk']}

    def get_queryset(self):
        return CartItem.objects \
                .filter(cart_id=self.kwargs['cart_pk']) \
                .select_related('product')
    


class CustomerViewset(CreateModelMixin,UpdateModelMixin,RetrieveModelMixin,GenericViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    @action(detail=False , methods=['GET','PUT'])
    def me(self, request):
        customer = Customer.objects.get(user_id = request.user.id)
        if self.request.method == 'GET':
            serializer = CustomerSerializer(customer)
            return Response(serializer.data)
        elif self.request.method == 'PUT':
            serializer = CustomerSerializer(customer, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

class OrderViewset(ModelViewSet):

    http_method_names = ['get','post','patch','delete','options','head']

    def get_permissions(self):
        if self.request.method in ['PATCH','DELETE']:
            return [IsAdminUser()]
        return[IsAuthenticated()]
    
    '''we overwrite the create method of mixins because the original one returns the serializer that recieves in first place.but we want to see the created order at the end,not the cart_id(serializer that we send).so we create the order by the createorder serializer but we return the order with order serializer at the end......hint: we use get_serializer_context method when we use the original create method not when we override it,so instead we give the context to the serializer object itself'''

    #overwrite create method of the createmodelmixin
    def create(self, request, *args, **kwargs):
        serializer = CreateOrderSerializer(data=request.data,context ={'user_id':self.request.user.id} ) #used creatorderserializer to create
        serializer.is_valid(raise_exception=True)
        order = serializer.save()      #the returend order of the serializer
        serializer = OrderSerializer(order)  #used orderserializer to return
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.request.method == 'POST':
           return CreateOrderSerializer
        elif self.request.method =='PATCH':
            return UpdateOrderSerializer 
        return OrderSerializer
    
    #def get_serializer_context(self):
        #return {'user_id':self.request.user.id}
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all()
        customer_id = Customer.objects.only('id').get(user_id = user.id)
        return Order.objects.filter(customer_id = customer_id)