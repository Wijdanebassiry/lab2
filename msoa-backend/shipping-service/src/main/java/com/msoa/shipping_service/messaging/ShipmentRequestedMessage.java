
package com.msoa.shipping_service.messaging;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Getter
@Setter
@NoArgsConstructor
public class ShipmentRequestedMessage {

    private String messageId;
    private String type;
    private Integer version;
    private String occurredAt;
    private String orderId;
    private String userId;
    private Customer customer;

    public void validate() {

        if (messageId == null || messageId.isBlank()) {
            throw new IllegalArgumentException("messageId is required");
        }

        UUID.fromString(messageId);

        if (!"shipment.requested".equals(type)) {
            throw new IllegalArgumentException("Invalid message type");
        }

        if (version == null || version != 1) {
            throw new IllegalArgumentException("Unsupported message version");
        }

        if (occurredAt == null || occurredAt.isBlank()) {
            throw new IllegalArgumentException("occurredAt is required");
        }

        Instant.parse(occurredAt);

        if (orderId == null || orderId.isBlank()) {
            throw new IllegalArgumentException("orderId is required");
        }

        if (userId == null || userId.isBlank()) {
            throw new IllegalArgumentException("userId is required");
        }

        if (customer == null
                || customer.getName() == null || customer.getName().isBlank()
                || customer.getAddress() == null || customer.getAddress().isBlank()
                || customer.getCity() == null || customer.getCity().isBlank()) {
            throw new IllegalArgumentException("Invalid customer information");
        }
    }

    @Getter
    @Setter
    @NoArgsConstructor
    public static class Customer {
        private String name;
        private String address;
        private String city;
    }
}
