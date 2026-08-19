# HomeCloud Java SDK

Maven: `com.homecloudlab:homecloud-sdk`  
Package: `com.homecloudlab.sdk`  
ADR: [ADR-052](https://github.com/HomeCloudLab/homecloud-infra/blob/master/docs/adr/adr-052-java-sdk.md)

Same HomeCloud product contract as Python, Node, and Go: SigV1 Access Keys, `~/.homecloud` credentials, typed HTTP errors. The **public API is idiomatic Java** (builders, records, unchecked exceptions). It is allowed to differ structurally. Documented safety fixes take precedence over copying unsafe behavior (no automatic retry of `MQ.send`).

`HomeCloud` is **thread-safe after construction** — reuse it (Spring `@Bean`). Interactive login lives on `HomeCloudAuth` and returns a **new** client.

## Install

Requires **Java 17+**.

```xml
<dependency>
  <groupId>com.homecloudlab</groupId>
  <artifactId>homecloud-sdk</artifactId>
  <version>0.5.10</version>
</dependency>
```

Until Maven Central (public GA), the artifact is on **GitHub Packages**. Add the repo and a GitHub token that can read `HomeCloudLab/homecloud-sdk` packages:

```xml
<repositories>
  <repository>
    <id>github-homecloud</id>
    <url>https://maven.pkg.github.com/HomeCloudLab/homecloud-sdk</url>
  </repository>
</repositories>
```

```xml
<!-- ~/.m2/settings.xml -->
<server>
  <id>github-homecloud</id>
  <username>YOUR_GITHUB_USERNAME</username>
  <password>YOUR_GITHUB_PAT</password>
</server>
```

## Usage

```java
import com.homecloudlab.sdk.HomeCloud;
import com.homecloudlab.sdk.UploadOptions;

HomeCloud client = HomeCloud.fromEnv();
client.so().upload("docs", UploadOptions.builder().filePath("./a.txt").key("a.txt").build());
client.mq().send("orders", Map.of("id", 1));
```

Explicit credentials:

```java
HomeCloud client = HomeCloud.fromCredentials("HCAK...", "secret");
```

Advanced:

```java
HomeCloud client = HomeCloud.builder()
    .apex("holab.abrdns.com")
    .accessKey("HCAK...", "secret")
    .requestTimeout(Duration.ofSeconds(30))
    .build();
```

## Errors

```java
try {
    client.so().headObject("docs", "missing.txt");
} catch (NotFoundException e) {
    System.out.println(e.getResourceType() + " " + e.getResource());
}
```

## Retry

GET/HEAD/PUT/DELETE and SO upload retry on 502/503/504 with exponential backoff + jitter. **`mq().send` does not retry** (duplicates). Management creates send `Idempotency-Key`.

## Tests

```bash
cd java && mvn test
```
