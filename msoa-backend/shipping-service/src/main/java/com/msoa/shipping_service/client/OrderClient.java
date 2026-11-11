
package com.msoa.shipping_service.client;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

@Component
public class OrderClient {

    private final RestTemplate restTemplate;
    private final String ordersUrl;

    public OrderClient(
            RestTemplateBuilder builder,
            @Value("${orders.url}") String ordersUrl
    ) {
        this.restTemplate = builder.build();
        this.ordersUrl = ordersUrl;
    }

    // Vérifier que la commande existe et qu'elle est payée
    public void verifyOrderIsPaid(String orderId, String authorization) {

        String url = ordersUrl + "/api/orders/" + orderId;

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set(HttpHeaders.AUTHORIZATION, authorization);

            HttpEntity<Void> entity = new HttpEntity<>(headers);

            JsonNode order = restTemplate.exchange(
                    url,
                    HttpMethod.GET,
                    entity,
                    JsonNode.class
            ).getBody();

            if (order == null || !order.has("status")
                    || order.get("status").isNull()) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_GATEWAY,
                        "Invalid response from Orders Service"
                );
            }

            String status = order.get("status").asText();

            if (!"PAID".equalsIgnoreCase(status)) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST,
                        "Order is not paid"
                );
            }

        } catch (HttpStatusCodeException e) {

            if (e.getStatusCode().value() == 404) {
                throw new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        "Order not found"
                );
            }

            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY,
                    "Orders Service returned an error"
            );

        } catch (ResourceAccessException e) {

            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "Orders Service is unavailable"
            );

        } catch (RestClientException e) {

            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY,
                    "Communication error with Orders Service"
            );
        }
    }

    // Synchroniser le statut de la commande dans Orders
    public void updateOrderStatus(
            String orderId,
            String status,
            String authorization
    ) {

        String url = ordersUrl + "/api/orders/" + orderId + "/status";

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set(HttpHeaders.AUTHORIZATION, authorization);
            headers.setContentType(MediaType.APPLICATION_JSON);

            Map<String, String> body = Map.of("status", status);

            HttpEntity<Map<String, String>> entity =
                    new HttpEntity<>(body, headers);

            restTemplate.exchange(
                    url,
                    HttpMethod.PATCH,
                    entity,
                    Void.class
            );

        } catch (ResourceAccessException e) {

            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "Orders Service is unavailable"
            );

        } catch (RestClientException e) {

            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY,
                    "Failed to update order status in Orders Service"
            );
        }
    }
}
