package com.example.service;

import org.springframework.stereotype.Service;

@Service
public class UserService {

    public String getUser(Long userId) {
        return "user-" + userId;
    }
}