
package com.msoa.shipping_service.service;

import com.msoa.shipping_service.client.OrderClient;
import com.msoa.shipping_service.dto.ShipmentRequest;
import com.msoa.shipping_service.dto.ShipmentResponse;
import com.msoa.shipping_service.dto.UpdateShipmentStatusRequest;
import com.msoa.shipping_service.entity.Shipment;
import com.msoa.shipping_service.entity.ShipmentStatus;
import com.msoa.shipping_service.messaging.ShipmentRequestedMessage;
import com.msoa.shipping_service.repository.ShipmentRepository;

import lombok.RequiredArgsConstructor;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
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

    // 3. Create shipment through REST
    public ShipmentResponse createShipment(
            ShipmentRequest request,
            String authorization
    ) {

        // Idempotency: return existing shipment if it already exists
        var existingShipment = shipmentRepository.findByOrderId(
                request.getOrderId()
        );

        if (existingShipment.isPresent()) {
            return toResponse(existingShipment.get());
        }

        // Verify order with Orders microservice using JWT
        orderClient.verifyOrderIsPaid(
                request.getOrderId(),
                authorization
        );

        // Create and save shipment
        Shipment savedShipment = createAndSaveShipment(
                request.getOrderId(),
                request.getAddress().getName(),
                request.getAddress().getAddress(),
                request.getAddress().getCity()
        );

        return toResponse(savedShipment);
    }

    // 4. Create shipment from RabbitMQ event
    @Transactional
    public ShipmentResponse createShipmentFromEvent(
            ShipmentRequestedMessage message
    ) {

        // Validate incoming message
        message.validate();

        // Idempotency: ignore duplicate order events
        var existingShipment = shipmentRepository.findByOrderId(
                message.getOrderId()
        );

        if (existingShipment.isPresent()) {
            return toResponse(existingShipment.get());
        }

        // Payments publishes this event only after successful payment
        Shipment savedShipment = createAndSaveShipment(
                message.getOrderId(),
                message.getCustomer().getName(),
                message.getCustomer().getAddress(),
                message.getCustomer().getCity()
        );

        return toResponse(savedShipment);
    }

    // 5. Common method to create and save a shipment
    private Shipment createAndSaveShipment(
            String orderId,
            String name,
            String address,
            String city
    ) {

        Shipment shipment = new Shipment();

        shipment.setOrderId(orderId);
        shipment.setName(name);
        shipment.setAddress(address);
        shipment.setCity(city);

        shipment.setTrackingNumber(
                "TRK-" + UUID.randomUUID().toString().substring(0, 8)
        );

        shipment.setStatus(ShipmentStatus.PREPARING);

        return shipmentRepository.save(shipment);
    }

    // 6. Update shipment status
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

        // Synchronize with Orders BEFORE changing local shipment status
        if (newStatus == ShipmentStatus.SHIPPED
                || newStatus == ShipmentStatus.DELIVERED) {

            orderClient.updateOrderStatus(
                    shipment.getOrderId(),
                    newStatus.name(),
                    authorization
            );
        }

        // Save only after successful synchronization
        shipment.setStatus(newStatus);

        Shipment updatedShipment = shipmentRepository.save(shipment);

        return toResponse(updatedShipment);
    }

    // 7. Convert Entity to Response DTO
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
