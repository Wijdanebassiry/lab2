package com.msoa.shipping_service.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;

@Getter
@Setter
@NoArgsConstructor
public class ShipmentRequest {

    @NotBlank
    private String orderId;

    @NotNull
    @Valid
    private AddressRequest address;

    @Getter
    @Setter
    @NoArgsConstructor
    public static class AddressRequest {

        @NotBlank
        private String name;

        @NotBlank
        private String address;

        @NotBlank
        private String city;
    }
}