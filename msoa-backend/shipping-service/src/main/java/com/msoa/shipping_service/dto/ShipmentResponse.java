package com.msoa.shipping_service.dto;

import com.msoa.shipping_service.entity.ShipmentStatus;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@AllArgsConstructor
public class ShipmentResponse {

    private Long id;
    private String orderId;
    private String trackingNumber;

    private String name;
    private String address;
    private String city;

    private ShipmentStatus status;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}