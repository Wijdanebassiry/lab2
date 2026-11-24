
package com.msoa.shipping_service.messaging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

import com.msoa.shipping_service.config.RabbitMQConfig;
import com.msoa.shipping_service.service.ShipmentService;

import com.rabbitmq.client.Channel;

import lombok.RequiredArgsConstructor;

import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
@RequiredArgsConstructor
public class ShipmentRequestedConsumer {

    private final ShipmentService shipmentService;
    private final ObjectMapper objectMapper;

    private static final int MAX_ATTEMPTS = 3;

    // Receive messages from RabbitMQ
    @RabbitListener(queues = RabbitMQConfig.QUEUE)
    public void consume(
            Message rabbitMessage,
            Channel channel
    ) throws IOException {

        long deliveryTag = rabbitMessage.getMessageProperties()
                .getDeliveryTag();

        ShipmentRequestedMessage message;

        // 1. Convert JSON into Java object
        try {
            message = objectMapper
                    .readerFor(ShipmentRequestedMessage.class)
                    .with(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
                    .readValue(rabbitMessage.getBody());

            // 2. Validate the message
            message.validate();

        } catch (JsonProcessingException | IllegalArgumentException e) {

            System.err.println(
                    "Invalid shipment message: " + e.getMessage()
            );

            // Reject invalid message and send it to DLQ
            channel.basicReject(deliveryTag, false);
            return;
        }

        // 3. Process the message with 3 attempts
        for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {

            try {

                // Save shipment in MySQL
                // If it already exists, the service returns the existing one
                shipmentService.createShipmentFromEvent(message);

                // 4. ACK only after successful processing
                channel.basicAck(deliveryTag, false);

                System.out.println(
                        "Shipment processed successfully for order: "
                                + message.getOrderId()
                );

                return;

            } catch (Exception e) {

                System.err.println(
                        "Shipment processing failed. Attempt "
                                + attempt + "/" + MAX_ATTEMPTS
                                + " - " + e.getMessage()
                );

                // If attempts remain, wait before retrying
                if (attempt < MAX_ATTEMPTS) {

                    try {
                        Thread.sleep(attempt * 1000L);

                    } catch (InterruptedException interruptedException) {

                        Thread.currentThread().interrupt();

                        channel.basicReject(deliveryTag, false);
                        return;
                    }
                }
            }
        }

        // 5. All attempts failed: reject and send to DLQ
        channel.basicReject(deliveryTag, false);

        System.err.println(
                "Message rejected after 3 attempts. Order: "
                        + message.getOrderId()
        );
    }
}
