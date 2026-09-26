package com.example.repository;

import org.springframework.stereotype.Repository;

@Repository
public class UserRepository {

    public String findById(Long id) {
        return "user-" + id;
    }
}