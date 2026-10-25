package example;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import static org.junit.jupiter.api.Assertions.assertEquals;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class HelloControllerTest {
    @LocalServerPort int port;
    private HttpResponse<String> get(String query) throws Exception {
        return HttpClient.newHttpClient().send(HttpRequest.newBuilder(
            URI.create("http://localhost:" + port + "/hello" + query)).GET().build(), HttpResponse.BodyHandlers.ofString());
    }
    @Test void missingNameReturns400() throws Exception { assertEquals(400, get("").statusCode()); }
    @Test void emptyNameReturns400() throws Exception { assertEquals(400, get("?name=").statusCode()); }
    @Test void blankNameReturns400() throws Exception { assertEquals(400, get("?name=%20%20").statusCode()); }
    @Test void validNamePreservesGreeting() throws Exception {
        HttpResponse<String> response = get("?name=Alice");
        assertEquals(200, response.statusCode());
        assertEquals("Hello, Alice", response.body());
    }
}
