**Project Nexus: Asynchronous Messaging using OmniBus**

**Authors:** Liam (Cloud Infrastructure Engineer) and Alex (Backend Engineer)
**Date:** 2023-01-26

## Introduction

Project Nexus aims to establish a scalable and reliable communication framework for our microservices architecture. One of the key components in achieving this goal is the OmniBus, a high-performance asynchronous messaging system built using Apache Kafka and RabbitMQ. This document provides a technical overview of the OmniBus, its architecture, and usage guidelines.

## Technical Details

The OmniBus is designed to handle a high volume of messages in a distributed environment, ensuring efficient data processing and minimizing latency. It consists of two main components:

### Producer and Consumer

- **Producer:** Responsible for sending messages to the message broker. Our implementation uses a combination of Apache Kafka and RabbitMQ, allowing us to leverage the strengths of each technology.
- **Consumer:** Responsible for processing messages from the message broker. Consumers can be configured to run in a distributed mode, using Apache Kafka's `group.id` feature to ensure message processing is handled in a deterministic and fault-tolerant manner.

### Message Broker

We use Apache Kafka as the primary message broker for its high-throughput and fault-tolerant nature. Kafka topics are used to categorize messages, and each topic is replicated across multiple brokers to ensure message durability.

RabbitMQ is used as a secondary message broker to provide an AMQP interface for legacy systems. This allows us to seamlessly integrate with existing messaging systems without disrupting our Kafka-based architecture.

## How-to use the component

To use the OmniBus in your application, follow these steps:

1. **Configure your producer:** Create a producer instance and configure it to connect to the message broker. You can use either the Kafka or RabbitMQ producer, depending on your use case.
2. **Send a message:** Use the producer to send a message to the desired topic or queue.
3. **Configure your consumer:** Create a consumer instance and configure it to connect to the message broker. You can use either the Kafka or RabbitMQ consumer, depending on your use case.
4. **Process messages:** Use the consumer to process messages from the topic or queue.

### Example Code (Producer)
```java
// Create a Kafka producer
KafkaProducer<String, String> producer = new KafkaProducer<>(
    new Properties()
        .put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092")
        .put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName())
        .put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName())
);

// Send a message
producer.send(new ProducerRecord<>("my_topic", "Hello, World!"));
```

### Example Code (Consumer)
```java
// Create a Kafka consumer
KafkaConsumer<String, String> consumer = new KafkaConsumer<>(
    new Properties()
        .put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092")
        .put(ConsumerConfig.GROUP_ID_CONFIG, "my_group")
        .put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName())
        .put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName())
);

// Subscribe to the topic
consumer.subscribe(Collections.singleton("my_topic"));

// Process messages
while (true) {
    ConsumerRecords<String, String> records = consumer.poll(100);
    for (ConsumerRecord<String, String> record : records) {
        System.out.println(record.value());
    }
    consumer.commitSync();
}
```

## Limitations/Gotchas

- **Message ordering:** Due to the distributed nature of the OmniBus, message ordering cannot be guaranteed. Use `kafka.message.timestamp.type=CreateTime` to ensure that messages are processed in the order they were produced.
- **Duplicate messages:** Use `kafka.retry.max.attempts=1` to prevent duplicate messages from being processed multiple times.
- **Broker configuration:** Ensure that the message broker is properly configured to handle the expected message volume and throughput.

**Cross-referencing:** This design was inspired by Project Sentinel, where Chloe (ML Engineer) previously worked on a related issue. Chloe reviewed this implementation and provided valuable feedback.

As a result, we are confident that the OmniBus will provide a reliable and scalable communication framework for Project Nexus.