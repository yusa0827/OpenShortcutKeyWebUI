void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("HELLO ESP32-S3!");
}
void loop() {
  Serial.println("tick");
  delay(1000);
}