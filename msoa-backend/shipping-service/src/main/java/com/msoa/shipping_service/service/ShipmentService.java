
package com.msoa.shipping_service.service;

import com.msoa.shipping_service.client.OrderClient;
import com.msoa.shipping_service.dto.ShipmentRequest;
import com.msoa.shipping_service.dto.ShipmentResponse;
import com.msoa.shipping_service.dto.UpdateShipmentStatusRequest;
import com.msoa.shipping_service.entity.Shipment;
import com.msoa.shipping_service.entity.ShipmentStatus;
import com.msoa.shipping_service.repository.ShipmentRepository;

import lombok.RequiredArgsConstructor;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ShipmentService {

    private final ShipmentRepository shipmentRepository;
    private final OrderClient orderClient;

    // 1. Get all shipments
    public List<ShipmentResponse> getAllShipments() {

        return shipmentRepository.findAll()
                .stream()
                .map(this::toResponse)
                .toList();
    }

    // 2. Get shipment by order ID
    public ShipmentResponse getShipmentByOrderId(String orderId) {

        Shipment shipment = shipmentRepository.findByOrderId(orderId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        "Shipment not found for this order"
                ));

        return toResponse(shipment);
    }

    // 3. Create shipment
    public ShipmentResponse createShipment(
            ShipmentRequest request,
            String authorization
    ) {

        // Check if shipment already exists
        if (shipmentRepository.findByOrderId(request.getOrderId()).isPresent()) {

            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "A shipment already exists for this order"
            );
        }

        // Verify order with Orders microservice using JWT
        orderClient.verifyOrderIsPaid(
                request.getOrderId(),
                authorization
        );

        // Create shipment entity
        Shipment shipment = new Shipment();

        shipment.setOrderId(request.getOrderId());
        shipment.setName(request.getAddress().getName());
        shipment.setAddress(request.getAddress().getAddress());
        shipment.setCity(request.getAddress().getCity());

        shipment.setTrackingNumber(
                "TRK-" + UUID.randomUUID().toString().substring(0, 8)
        );

        shipment.setStatus(ShipmentStatus.PREPARING);

        // Save in MySQL
        Shipment savedShipment = shipmentRepository.save(shipment);

        return toResponse(savedShipment);
    }

    // 4. Update shipment status
    public ShipmentResponse updateShipmentStatus(
            Long id,
            UpdateShipmentStatusRequest request,
            String authorization
    ) {

        Shipment shipment = shipmentRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        "Shipment not found"
                ));

        ShipmentStatus newStatus = request.getStatus();

        // Check valid status transition
        boolean validTransition =
                (shipment.getStatus() == ShipmentStatus.PREPARING
                        && newStatus == ShipmentStatus.SHIPPED)

                        || (shipment.getStatus() == ShipmentStatus.SHIPPED
                        && newStatus == ShipmentStatus.IN_TRANSIT)

                        || (shipment.getStatus() == ShipmentStatus.IN_TRANSIT
                        && newStatus == ShipmentStatus.DELIVERED);

        if (!validTransition) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Invalid shipment status transition"
            );
        }

        // Synchronize with Orders BEFORE changing the local shipment status
        if (newStatus == ShipmentStatus.SHIPPED
                || newStatus == ShipmentStatus.DELIVERED) {

            orderClient.updateOrderStatus(
                    shipment.getOrderId(),
                    newStatus.name(),
                    authorization
            );
        }

        // Only update Shipping after successful synchronization
        shipment.setStatus(newStatus);

        Shipment updatedShipment = shipmentRepository.save(shipment);

        return toResponse(updatedShipment);
    }

    // Convert Entity to Response DTO
    private ShipmentResponse toResponse(Shipment shipment) {

        return new ShipmentResponse(
                shipment.getId(),
                shipment.getOrderId(),
                shipment.getTrackingNumber(),
                shipment.getName(),
                shipment.getAddress(),
                shipment.getCity(),
                shipment.getStatus(),
                shipment.getCreatedAt(),
                shipment.getUpdatedAt()
        );
    }
}
