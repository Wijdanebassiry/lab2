
package com.msoa.shipping_service.messaging;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.msoa.shipping_service.service.ShipmentService;
import com.rabbitmq.client.Channel;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;

import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ShipmentRequestedConsumerTest {

    @Mock
    private ShipmentService shipmentService;

    @Mock
    private Channel channel;

    private ShipmentRequestedConsumer consumer;

    @BeforeEach
    void setUp() {
        consumer = new ShipmentRequestedConsumer(
                shipmentService,
                new ObjectMapper()
        );
    }

    private Message createMessage(String json) {

        MessageProperties properties = new MessageProperties();
        properties.setDeliveryTag(1L);

        return new Message(
                json.getBytes(StandardCharsets.UTF_8),
                properties
        );
    }

    private String validMessage() {

        return """
                {
                  "messageId": "550e8400-e29b-41d4-a716-446655440000",
                  "type": "shipment.requested",
                  "version": 1,
                  "occurredAt": "2026-11-24T10:00:00Z",
                  "orderId": "order-123",
                  "userId": "user-123",
                  "customer": {
                    "name": "Demo Customer",
                    "address": "123 Main Street",
                    "city": "Casablanca"
                  }
                }
                """;
    }

    // TEST 1: Normal message -> process and ACK
    @Test
    void consume_shouldProcessValidMessageAndAcknowledge()
            throws IOException {

        Message message = createMessage(validMessage());

        consumer.consume(message, channel);

        verify(shipmentService, times(1))
                .createShipmentFromEvent(any(ShipmentRequestedMessage.class));

        verify(channel).basicAck(1L, false);

        verify(channel, never()).basicReject(anyLong(), anyBoolean());
    }

    // TEST 2: Duplicate message -> ACK without creating another shipment
    @Test
    void consume_shouldAcknowledgeDuplicateMessage()
            throws IOException {

        Message message = createMessage(validMessage());

        // Simulate receiving the same message twice
        consumer.consume(message, channel);
        consumer.consume(message, channel);

        // Both deliveries are processed by the idempotent service
        verify(shipmentService, times(2))
                .createShipmentFromEvent(any(ShipmentRequestedMessage.class));

        // Both messages must be acknowledged
        verify(channel, times(2)).basicAck(1L, false);

        // No rejection
        verify(channel, never()).basicReject(anyLong(), anyBoolean());
    }

    // TEST 3: Invalid message -> reject and send to DLQ
    @Test
    void consume_shouldRejectInvalidMessage()
            throws IOException {

        String invalidJson = """
                {
                  "messageId": "invalid-id",
                  "type": "wrong.type",
                  "version": 99
                }
                """;

        Message message = createMessage(invalidJson);

        consumer.consume(message, channel);

        verify(channel).basicReject(1L, false);

        verify(channel, never()).basicAck(anyLong(), anyBoolean());

        verifyNoInteractions(shipmentService);
    }
    // TEST 4: Processing fails 3 times -> reject message to DLQ
    @Test
    void consume_shouldRetryThreeTimesThenRejectMessage()
            throws IOException {

        Message message = createMessage(validMessage());

        // Simulate a failure on every attempt
        doThrow(new RuntimeException("Simulated database error"))
                .when(shipmentService)
                .createShipmentFromEvent(any(ShipmentRequestedMessage.class));

        // Consume the message
        consumer.consume(message, channel);

        // Verify exactly 3 attempts
        verify(shipmentService, times(3))
                .createShipmentFromEvent(any(ShipmentRequestedMessage.class));

        // Reject after the third failure
        verify(channel).basicReject(1L, false);

        // Never acknowledge a failed message
        verify(channel, never()).basicAck(anyLong(), anyBoolean());
    }
}
