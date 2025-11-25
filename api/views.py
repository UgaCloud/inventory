from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from api.serializers import TransferRequestSerializer, StockTransferSerializer, AvailableStockSerializer
from app.services.transfer_service import create_transfer_request, approve_transfer_request, complete_stock_transfer
from app.models.products import Inventory, Product
from app.models.transactions import TransferRequest, StockTransfer


class CreateTransferRequestAPI(APIView):
	permission_classes = [permissions.IsAuthenticated]

	def post(self, request):
		# Expect payload: from_store, to_store, items: [{product, quantity, units}]
		data = request.data
		items = data.get('items', [])
		try:
			tr = create_transfer_request(request.user, data.get('from_store'), data.get('to_store'), items)
			serializer = TransferRequestSerializer(tr)
			return Response(serializer.data, status=status.HTTP_201_CREATED)
		except ValidationError as e:
			return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
			return Response({'detail': 'Server error: ' + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApproveTransferRequestAPI(APIView):
	permission_classes = [permissions.IsAuthenticated]

	def post(self, request):
		tr_id = request.data.get('transfer_request_id')
		# rudimentary permission check: member of 'Manager' or 'Admin' group
		user = request.user
		if not (user.is_superuser or user.groups.filter(name__in=['Admin', 'Manager']).exists()):
			return Response({'detail': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)

		try:
			st = approve_transfer_request(tr_id, user)
			serializer = StockTransferSerializer(st)
			return Response(serializer.data)
		except TransferRequest.DoesNotExist:
			return Response({'detail': 'TransferRequest not found'}, status=status.HTTP_404_NOT_FOUND)
		except ValidationError as e:
			return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CreateStockTransferAPI(APIView):
	permission_classes = [permissions.IsAuthenticated]

	def post(self, request):
		# Create ad-hoc StockTransfer (direct transfer)
		data = request.data
		try:
			st = StockTransfer.objects.create(
				from_store=data.get('from_store'),
				to_store=data.get('to_store'),
				status='pending',
				created_by=request.user
			)
			# items creation omitted here — UI should call dedicated endpoint or use approve flow
			serializer = StockTransferSerializer(st)
			return Response(serializer.data, status=status.HTTP_201_CREATED)
		except Exception as e:
			return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CompleteStockTransferAPI(APIView):
	permission_classes = [permissions.IsAuthenticated]

	def post(self, request):
		transfer_id = request.data.get('transfer_id')
		# permission check could be tightened
		try:
			st = complete_stock_transfer(transfer_id, request.user)
			serializer = StockTransferSerializer(st)
			return Response(serializer.data)
		except StockTransfer.DoesNotExist:
			return Response({'detail': 'StockTransfer not found'}, status=status.HTTP_404_NOT_FOUND)
		except ValidationError as e:
			return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StartStockTransferAPI(APIView):
	permission_classes = [permissions.IsAuthenticated]

	def post(self, request):
		transfer_id = request.data.get('transfer_id')
		try:
			# Use service layer to start
			from app.services.transfer_service import start_stock_transfer
			st = start_stock_transfer(transfer_id, request.user)
			serializer = StockTransferSerializer(st)
			return Response(serializer.data)
		except StockTransfer.DoesNotExist:
			return Response({'detail': 'StockTransfer not found'}, status=status.HTTP_404_NOT_FOUND)
		except ValidationError as e:
			return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
			return Response({'detail': 'Server error: ' + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AvailableStockAPI(APIView):
	permission_classes = [permissions.AllowAny]

	def get(self, request, store_id, product_id):
		try:
			inv = Inventory.objects.filter(store_id=store_id, product_id=product_id).first()
			available = inv.quantity_in_stock if inv else 0
			ser = AvailableStockSerializer({'product_id': product_id, 'store_id': store_id, 'available': available})
			return Response(ser.data)
		except Exception as e:
			return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

