/*
  Blink Sketch for Arduino UNO Q

  This sketch makes the onboard LED blink with 1 second on and 1 second off.

  The Arduino UNO Q uses LED_BUILTIN for the onboard LED.
*/

void setup() {
  // Initialize the LED pin as an output
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  // Turn the LED on
  digitalWrite(LED_BUILTIN, HIGH);

  // Wait for 1 second (1000 milliseconds)
  delay(1000);

  // Turn the LED off
  digitalWrite(LED_BUILTIN, LOW);

  // Wait for 1 second (1000 milliseconds)
  delay(1000);
}
