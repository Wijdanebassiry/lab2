
package com.msoa.shipping_service.security;

import com.msoa.shipping_service.client.AuthClient;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    // Attribut permettant de transmettre le header aux autres couches
    public static final String AUTHORIZATION_ATTRIBUTE =
            "shipping.authorization";

    private final AuthClient authClient;

    public JwtAuthenticationFilter(AuthClient authClient) {
        this.authClient = authClient;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return "OPTIONS".equalsIgnoreCase(request.getMethod());
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {

        String authorization = request.getHeader("Authorization");

        if (authorization == null
                || !authorization.startsWith("Bearer ")
                || authorization.substring(7).isBlank()) {

            sendError(
                    response,
                    HttpStatus.UNAUTHORIZED,
                    "Missing or invalid Authorization header"
            );
            return;
        }

        String token = authorization.substring(7).trim();

        try {
            // Vérifier le token auprès du service Auth
            authClient.verifyToken(token);

        } catch (ResponseStatusException e) {

            sendError(
                    response,
                    HttpStatus.valueOf(e.getStatusCode().value()),
                    e.getReason()
            );
            return;
        }

        // Conserver le header Authorization pour les appels vers Orders
        request.setAttribute(
                AUTHORIZATION_ATTRIBUTE,
                authorization
        );

        // Token valide : continuer vers le Controller
        filterChain.doFilter(request, response);
    }

    private void sendError(
            HttpServletResponse response,
            HttpStatus status,
            String message
    ) throws IOException {

        response.setStatus(status.value());
        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");

        response.getWriter().write(
                "{\"message\":\"" + message
                        + "\",\"error\":\"" + status.name() + "\"}"
        );
    }
}
