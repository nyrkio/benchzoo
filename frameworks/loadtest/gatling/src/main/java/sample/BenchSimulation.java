package sample;

import static io.gatling.javaapi.core.CoreDsl.*;
import static io.gatling.javaapi.http.HttpDsl.*;

import io.gatling.javaapi.core.ScenarioBuilder;
import io.gatling.javaapi.core.Simulation;
import io.gatling.javaapi.http.HttpProtocolBuilder;
import java.time.Duration;

public class BenchSimulation extends Simulation {

  HttpProtocolBuilder httpProtocol =
      http.baseUrl("http://localhost:8080").acceptHeader("text/html");

  ScenarioBuilder scn = scenario("homepage").exec(http("get /").get("/"));

  {
    setUp(scn.injectOpen(constantUsersPerSec(10).during(Duration.ofSeconds(5))))
        .protocols(httpProtocol);
  }
}
