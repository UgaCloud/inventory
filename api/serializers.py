 
from rest_framework import serializers
from app.models.transactions import TransferRequest, TransferRequestItem, StockTransfer, StockTransferItem
from app.models.products import Inventory


class TransferRequestItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferRequestItem
        fields = ['id', 'product', 'quantity', 'units']


class TransferRequestSerializer(serializers.ModelSerializer):
    items = TransferRequestItemSerializer(many=True)

    class Meta:
        model = TransferRequest
        fields = ['id', 'requested_by', 'from_store', 'to_store', 'status', 'request_date', 'approved_by', 'approved_date', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        tr = TransferRequest.objects.create(**validated_data)
        for item in items_data:
            TransferRequestItem.objects.create(transfer_request=tr, **item)
        return tr


class StockTransferItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockTransferItem
        fields = ['id', 'product', 'quantity', 'units']


class StockTransferSerializer(serializers.ModelSerializer):
    items = StockTransferItemSerializer(many=True, read_only=True)

    class Meta:
        model = StockTransfer
        fields = ['id', 'transfer_request', 'from_store', 'to_store', 'status', 'created_by', 'items']


class AvailableStockSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    store_id = serializers.IntegerField()
    available = serializers.IntegerField()
