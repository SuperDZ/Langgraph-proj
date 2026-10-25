package example;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HelloController {
    @GetMapping("/hello")
    public ResponseEntity<String> hello(@RequestParam(required = false) String name) {
        return ResponseEntity.ok("Hello, " + name.trim());
    }
}
