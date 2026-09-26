package com.example.controller;

import com.example.service.UserService;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    public String getUser(Long userId) {
        return userService.getUser(userId);
    }
}