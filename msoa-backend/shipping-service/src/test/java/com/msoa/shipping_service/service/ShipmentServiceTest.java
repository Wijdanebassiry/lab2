
package com.msoa.shipping_service.service;

import com.msoa.shipping_service.client.OrderClient;
import com.msoa.shipping_service.dto.ShipmentRequest;
import com.msoa.shipping_service.dto.ShipmentResponse;
import com.msoa.shipping_service.dto.UpdateShipmentStatusRequest;
import com.msoa.shipping_service.entity.Shipment;
import com.msoa.shipping_service.entity.ShipmentStatus;
import com.msoa.shipping_service.repository.ShipmentRepository;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import com.msoa.shipping_service.messaging.ShipmentRequestedMessage;

@ExtendWith(MockitoExtension.class)
class ShipmentServiceTest {

    private static final String AUTHORIZATION = "Bearer test-token";

    @Mock
    private ShipmentRepository shipmentRepository;

    @Mock
    private OrderClient orderClient;

    @InjectMocks
    private ShipmentService shipmentService;

    // Helper: create a shipment request
    private ShipmentRequest createRequest(String orderId) {

        ShipmentRequest request = new ShipmentRequest();
        request.setOrderId(orderId);

        ShipmentRequest.AddressRequest address =
                new ShipmentRequest.AddressRequest();

        address.setName("Demo Customer");
        address.setAddress("123 Main Street");
        address.setCity("Casablanca");

        request.setAddress(address);

        return request;
    }

    // Helper: create a shipment entity
    private Shipment createShipment(ShipmentStatus status) {

        Shipment shipment = new Shipment();

        shipment.setId(1L);
        shipment.setOrderId("order-123");
        shipment.setTrackingNumber("TRK-12345678");
        shipment.setName("Demo Customer");
        shipment.setAddress("123 Main Street");
        shipment.setCity("Casablanca");
        shipment.setStatus(status);

        return shipment;
    }

    // Helper: create a status update request
    private UpdateShipmentStatusRequest statusRequest(
            ShipmentStatus status) {

        UpdateShipmentStatusRequest request =
                new UpdateShipmentStatusRequest();

        request.setStatus(status);

        return request;
    }

    // TEST 1: Successful shipment creation
    @Test
    void createShipment_shouldSucceedWhenOrderIsPaid() {

        ShipmentRequest request = createRequest("order-123");

        when(shipmentRepository.findByOrderId("order-123"))
                .thenReturn(Optional.empty());

        when(shipmentRepository.save(any(Shipment.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        ShipmentResponse response =
                shipmentService.createShipment(request, AUTHORIZATION);

        ArgumentCaptor<Shipment> captor =
                ArgumentCaptor.forClass(Shipment.class);

        verify(orderClient).verifyOrderIsPaid(
                "order-123",
                AUTHORIZATION
        );

        verify(shipmentRepository).save(captor.capture());

        Shipment saved = captor.getValue();

        assertNotNull(response);
        assertEquals("order-123", saved.getOrderId());
        assertEquals("Demo Customer", saved.getName());
        assertEquals("Casablanca", saved.getCity());
        assertEquals(ShipmentStatus.PREPARING, saved.getStatus());
        assertTrue(saved.getTrackingNumber().startsWith("TRK-"));
    }


    // TEST 2: Duplicate shipment - return existing shipment
    @Test
    void createShipment_shouldReturnExistingShipmentForDuplicateOrder() {

        ShipmentRequest request = createRequest("order-123");

        Shipment existingShipment = createShipment(ShipmentStatus.PREPARING);

        when(shipmentRepository.findByOrderId("order-123"))
                .thenReturn(Optional.of(existingShipment));

        ShipmentResponse response =
                shipmentService.createShipment(request, AUTHORIZATION);

        // The existing shipment must be returned
        assertNotNull(response);

        // No new shipment must be created
        verify(shipmentRepository, never()).save(any(Shipment.class));

        // Orders must not be called again
        verify(orderClient, never()).verifyOrderIsPaid(
                anyString(),
                anyString()
        );
    }


    // TEST 3: Order is not paid
    @Test
    void createShipment_shouldRejectUnpaidOrder() {

        ShipmentRequest request = createRequest("order-123");

        when(shipmentRepository.findByOrderId("order-123"))
                .thenReturn(Optional.empty());

        doThrow(new ResponseStatusException(
                HttpStatus.BAD_REQUEST,
                "Order is not paid"
        )).when(orderClient).verifyOrderIsPaid(
                "order-123",
                AUTHORIZATION
        );

        ResponseStatusException exception =
                assertThrows(
                        ResponseStatusException.class,
                        () -> shipmentService.createShipment(
                                request,
                                AUTHORIZATION
                        )
                );

        assertEquals(HttpStatus.BAD_REQUEST, exception.getStatusCode());

        verify(shipmentRepository, never()).save(any(Shipment.class));
    }

    // TEST 4: PREPARING -> SHIPPED
    @Test
    void updateStatus_shouldAllowPreparingToShipped() {

        Shipment shipment = createShipment(ShipmentStatus.PREPARING);

        when(shipmentRepository.findById(1L))
                .thenReturn(Optional.of(shipment));

        when(shipmentRepository.save(any(Shipment.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        ShipmentResponse response =
                shipmentService.updateShipmentStatus(
                        1L,
                        statusRequest(ShipmentStatus.SHIPPED),
                        AUTHORIZATION
                );

        assertNotNull(response);
        assertEquals(ShipmentStatus.SHIPPED, shipment.getStatus());

        verify(orderClient).updateOrderStatus(
                "order-123",
                "SHIPPED",
                AUTHORIZATION
        );

        verify(shipmentRepository).save(shipment);
    }

    // TEST 5: SHIPPED -> IN_TRANSIT
    @Test
    void updateStatus_shouldAllowShippedToInTransitWithoutCallingOrders() {

        Shipment shipment = createShipment(ShipmentStatus.SHIPPED);

        when(shipmentRepository.findById(1L))
                .thenReturn(Optional.of(shipment));

        when(shipmentRepository.save(any(Shipment.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        shipmentService.updateShipmentStatus(
                1L,
                statusRequest(ShipmentStatus.IN_TRANSIT),
                AUTHORIZATION
        );

        assertEquals(ShipmentStatus.IN_TRANSIT, shipment.getStatus());

        verify(orderClient, never()).updateOrderStatus(
                anyString(),
                anyString(),
                anyString()
        );

        verify(shipmentRepository).save(shipment);
    }

    // TEST 6: IN_TRANSIT -> DELIVERED
    @Test
    void updateStatus_shouldAllowInTransitToDelivered() {

        Shipment shipment = createShipment(ShipmentStatus.IN_TRANSIT);

        when(shipmentRepository.findById(1L))
                .thenReturn(Optional.of(shipment));

        when(shipmentRepository.save(any(Shipment.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        ShipmentResponse response =
                shipmentService.updateShipmentStatus(
                        1L,
                        statusRequest(ShipmentStatus.DELIVERED),
                        AUTHORIZATION
                );

        assertNotNull(response);
        assertEquals(ShipmentStatus.DELIVERED, shipment.getStatus());

        verify(orderClient).updateOrderStatus(
                "order-123",
                "DELIVERED",
                AUTHORIZATION
        );

        verify(shipmentRepository).save(shipment);
    }

    // TEST 7: Invalid status transition
    @Test
    void updateStatus_shouldRejectInvalidTransition() {

        Shipment shipment = createShipment(ShipmentStatus.PREPARING);

        when(shipmentRepository.findById(1L))
                .thenReturn(Optional.of(shipment));

        ResponseStatusException exception =
                assertThrows(
                        ResponseStatusException.class,
                        () -> shipmentService.updateShipmentStatus(
                                1L,
                                statusRequest(ShipmentStatus.DELIVERED),
                                AUTHORIZATION
                        )
                );

        assertEquals(HttpStatus.BAD_REQUEST, exception.getStatusCode());

        verify(orderClient, never()).updateOrderStatus(
                anyString(),
                anyString(),
                anyString()
        );

        verify(shipmentRepository, never()).save(any(Shipment.class));
    }

    // TEST 8: Shipment does not exist
    @Test
    void updateStatus_shouldReturnNotFoundWhenShipmentDoesNotExist() {

        when(shipmentRepository.findById(99L))
                .thenReturn(Optional.empty());

        ResponseStatusException exception =
                assertThrows(
                        ResponseStatusException.class,
                        () -> shipmentService.updateShipmentStatus(
                                99L,
                                statusRequest(ShipmentStatus.SHIPPED),
                                AUTHORIZATION
                        )
                );

        assertEquals(HttpStatus.NOT_FOUND, exception.getStatusCode());

        verify(orderClient, never()).updateOrderStatus(
                anyString(),
                anyString(),
                anyString()
        );
    }

    // TEST 9: Orders fails when updating to SHIPPED
    @Test
    void updateStatus_shouldNotChangeShipmentWhenOrdersFails() {

        Shipment shipment = createShipment(ShipmentStatus.PREPARING);

        when(shipmentRepository.findById(1L))
                .thenReturn(Optional.of(shipment));

        doThrow(new ResponseStatusException(
                HttpStatus.BAD_GATEWAY,
                "Failed to update order status in Orders Service"
        )).when(orderClient).updateOrderStatus(
                "order-123",
                "SHIPPED",
                AUTHORIZATION
        );

        ResponseStatusException exception =
                assertThrows(
                        ResponseStatusException.class,
                        () -> shipmentService.updateShipmentStatus(
                                1L,
                                statusRequest(ShipmentStatus.SHIPPED),
                                AUTHORIZATION
                        )
                );

        assertEquals(HttpStatus.BAD_GATEWAY, exception.getStatusCode());

        // The local shipment status must remain PREPARING
        assertEquals(ShipmentStatus.PREPARING, shipment.getStatus());

        // No save must happen
        verify(shipmentRepository, never()).save(any(Shipment.class));
    }

    // TEST 10: RabbitMQ duplicate event - no second shipment created
    @Test
    void createShipmentFromEvent_shouldIgnoreDuplicateOrderId() {

        // Create a valid RabbitMQ message
        ShipmentRequestedMessage message =
                new ShipmentRequestedMessage();

        message.setMessageId(
                "550e8400-e29b-41d4-a716-446655440000"
        );
        message.setType("shipment.requested");
        message.setVersion(1);
        message.setOccurredAt("2026-11-24T10:00:00Z");
        message.setOrderId("order-123");
        message.setUserId("user-123");

        ShipmentRequestedMessage.Customer customer =
                new ShipmentRequestedMessage.Customer();

        customer.setName("Demo Customer");
        customer.setAddress("123 Main Street");
        customer.setCity("Casablanca");

        message.setCustomer(customer);

        // Simulate that this order already has a shipment
        Shipment existingShipment =
                createShipment(ShipmentStatus.PREPARING);

        when(shipmentRepository.findByOrderId("order-123"))
                .thenReturn(Optional.of(existingShipment));

        // Process the RabbitMQ event
        ShipmentResponse response =
                shipmentService.createShipmentFromEvent(message);

        // The existing shipment must be returned
        assertNotNull(response);

        // No second shipment must be saved
        verify(shipmentRepository, never())
                .save(any(Shipment.class));

        // Orders must not be called for an event
        verifyNoInteractions(orderClient);
    }

}
