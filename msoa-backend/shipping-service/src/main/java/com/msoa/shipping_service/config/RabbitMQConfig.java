
package com.msoa.shipping_service.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    // Names defined in CONTRACTS.md
    public static final String EXCHANGE = "shipping.exchange";
    public static final String DLX = "shipping.dlx";
    public static final String QUEUE = "shipment.requests";
    public static final String DLQ = "shipment.requests.dlq";
    public static final String ROUTING_KEY = "shipment.requested";

    // Main exchange
    @Bean
    public DirectExchange shippingExchange() {
        return new DirectExchange(EXCHANGE, true, false);
    }

    // Dead Letter Exchange
    @Bean
    public DirectExchange shippingDlx() {
        return new DirectExchange(DLX, true, false);
    }

    // Main queue with Dead Letter configuration
    @Bean
    public Queue shipmentRequestsQueue() {
        return QueueBuilder.durable(QUEUE)
                .deadLetterExchange(DLX)
                .deadLetterRoutingKey(DLQ)
                .build();
    }

    // Dead Letter Queue
    @Bean
    public Queue shipmentRequestsDlq() {
        return QueueBuilder.durable(DLQ).build();
    }

    // Main binding
    @Bean
    public Binding shipmentRequestsBinding() {
        return BindingBuilder
                .bind(shipmentRequestsQueue())
                .to(shippingExchange())
                .with(ROUTING_KEY);
    }

    // Dead Letter binding
    @Bean
    public Binding shipmentRequestsDlqBinding() {
        return BindingBuilder
                .bind(shipmentRequestsDlq())
                .to(shippingDlx())
                .with(DLQ);
    }
}
