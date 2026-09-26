package com.example.controller;

import com.example.service.WebPageTranslateService;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class WebPageTranslateController {

    private final WebPageTranslateService webPageTranslateService;

    public WebPageTranslateController(
            WebPageTranslateService webPageTranslateService) {
        this.webPageTranslateService = webPageTranslateService;
    }

    public String translate(String text) {
        return webPageTranslateService.translate(text);
    }
}