
package com.msoa.shipping_service.controller;

import com.msoa.shipping_service.dto.ShipmentRequest;
import com.msoa.shipping_service.dto.ShipmentResponse;
import com.msoa.shipping_service.dto.UpdateShipmentStatusRequest;
import com.msoa.shipping_service.security.JwtAuthenticationFilter;
import com.msoa.shipping_service.service.ShipmentService;

import jakarta.validation.Valid;

import lombok.RequiredArgsConstructor;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/shipments")
@RequiredArgsConstructor
@CrossOrigin(origins = "http://localhost:5173")
public class ShipmentController {

    private final ShipmentService shipmentService;

    // GET /api/shipments
    @GetMapping
    public ResponseEntity<List<ShipmentResponse>> getAllShipments() {

        return ResponseEntity.ok(
                shipmentService.getAllShipments()
        );
    }

    // GET /api/shipments/order/{orderId}
    @GetMapping("/order/{orderId}")
    public ResponseEntity<ShipmentResponse> getShipmentByOrderId(
            @PathVariable String orderId
    ) {

        return ResponseEntity.ok(
                shipmentService.getShipmentByOrderId(orderId)
        );
    }

    // POST /api/shipments
    @PostMapping
    public ResponseEntity<ShipmentResponse> createShipment(
            @Valid @RequestBody ShipmentRequest request,
            @RequestAttribute(
                    JwtAuthenticationFilter.AUTHORIZATION_ATTRIBUTE
            ) String authorization
    ) {

        ShipmentResponse response =
                shipmentService.createShipment(request, authorization);

        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(response);
    }

    // PATCH /api/shipments/{id}/status
    @PatchMapping("/{id}/status")
    public ResponseEntity<ShipmentResponse> updateShipmentStatus(
            @PathVariable Long id,
            @Valid @RequestBody UpdateShipmentStatusRequest request,
            @RequestAttribute(
                    JwtAuthenticationFilter.AUTHORIZATION_ATTRIBUTE
            ) String authorization
    ) {

        return ResponseEntity.ok(
                shipmentService.updateShipmentStatus(
                        id,
                        request,
                        authorization
                )
        );
    }
}
