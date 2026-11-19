
package com.msoa.shipping_service.client;

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

@Component
public class AuthClient {

    private final RestTemplate restTemplate;
    private final String authUrl;

    public AuthClient(
            RestTemplateBuilder builder,
            @Value("${auth.url}") String authUrl
    ) {
        this.restTemplate = builder.build();
        this.authUrl = authUrl;
    }

    public void verifyToken(String token) {

        String url = authUrl + "/api/auth/me";

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);
        headers.setAccept(
                java.util.Collections.singletonList(MediaType.APPLICATION_JSON)
        );

        HttpEntity<Void> request = new HttpEntity<>(headers);

        try {

            restTemplate.exchange(
                    url,
                    HttpMethod.GET,
                    request,
                    String.class
            );

        } catch (HttpStatusCodeException e) {

            if (e.getStatusCode().value() == 401) {
                throw new ResponseStatusException(
                        HttpStatus.UNAUTHORIZED,
                        "Invalid or expired token"
                );
            }

            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "Auth Service returned an error"
            );

        } catch (ResourceAccessException e) {

            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "Auth Service is unavailable"
            );

        } catch (RestClientException e) {

            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "Communication error with Auth Service"
            );
        }
    }
}
