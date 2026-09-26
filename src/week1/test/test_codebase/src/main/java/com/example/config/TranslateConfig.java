package com.example.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

@Configuration
public class TranslateConfig {

    @Value("${translate.api.host}")
    private String host;

    @Value("${translate.api.access-key}")
    private String accessKey;

    public String getHost() {
        return host;
    }

    public String getAccessKey() {
        return accessKey;
    }
}