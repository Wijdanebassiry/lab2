package com.msoa.shipping_service.dto;

import com.msoa.shipping_service.entity.ShipmentStatus;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;

@Getter
@Setter
@NoArgsConstructor
public class UpdateShipmentStatusRequest {

    @NotNull
    private ShipmentStatus status;
}