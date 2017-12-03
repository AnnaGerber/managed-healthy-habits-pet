import machine
import time
import ubinascii
import webrepl
import oled
import soundfx
import lights
import ujson
from umqtt.simple import MQTTClient

rtc = machine.RTC()
currentStatus = 'good'

def remind(status='sleep'):
  global currentStatus
  currentStatus = status
  updateEyes(status)
  if status != 'sleep':
    # make a sound
    soundfx.question()
    # light up
    lights.randomWipe()


def updateEyes(status):
  # eyes indicate current status
  if status == 'sleep':
    beSleepy()
  elif status == 'fair':
    oled.pupils()
  elif status == 'good':
    oled.love()
  elif status == 'great':
    oled.bigLove()

def updatePet(topic, msg):
  # update the pet status based on message received from backend
  print(msg)
  status = ujson.load(msg).status
  remind(status)

def sleepDevice():
  global rtc
  # sleep for twenty minutes
  rtc.alarm(rtc.ALARM0, 120000)
  machine.deepsleep()

def rebootDevice():
  # trigger device to hard reset
  machine.reset()

def factoryReset():
  # reset device to 'good'
  global currentStatus
  currentStatus = 'good'
  updateEyes(currentStatus)

def beHappy():
  global currentStatus
  # hearts in eyes, clear lights and make a happy sound
  lights.clearWipe()
  oled.heartBeat()
  soundfx.happy()
  time.sleep(0.5)
  updateEyes(currentStatus)
  

def beSleepy():
  # clear lights if on
  lights.clearWipe()
  # sleepy eyes
  oled.sleepy() 

def main():
  rtc.irq(trigger=rtc.ALARM0, wake=machine.DEEPSLEEP)
  button = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
  payload = {'responded': True}
  deviceData = {'d': { 'lifetime': 0, 'supports': { 'deviceActions': True }}}
  orgid = "your 6 character org id"
  token = "your token"
  user = "use-token-auth"
  # Make sure this matches up with the device type you configured through the IoT platform
  deviceType = "ESP8266"
  # Change to match your device Id
  deviceId = "HealthyHabitPet"

  server = '{}.messaging.internetofthings.ibmcloud.com'.format(orgid)
  clientId = 'd:{}:{}:{}'.format(orgid, deviceType, deviceId)
  try:
    # SSL would be the preferred option however there is currently an issue with
    # MicroPython's umqtt.simple - non blocking check_msg is not working over SSL
    # For SSL add port = 8883, ssl = True
    client = MQTTClient(clientId, server, user=user, password=token)
    
  except:
    print('MQTT client setup error')

  try:
    client.set_callback(updatePet)
    
  except:
    print('MQTT callback error')
  
  buttonPressStarted = 0
  pendingNotification = False

  if machine.reset_cause() == machine.DEEPSLEEP_RESET:
    print("device woke up from sleep")
    reminded = True
  else:
    # only trigger initial reminder on hard reset
    reminded = False

  counter = 0

  while True:
    counter = counter + 1
    
    # every so many runs through the loop, connect to the MQTT broker to publish and check for messages
    # prevents repeated button press spam
    if counter >= 1000:
      counter = 0
      # trigger remind behaviour on startup
      if (reminded == False):
        remind('good')
        reminded = True

      client.connect()

      print("publishing to managed device topic")
      client.publish(b"iotdevice-1/mgmt/manage", ujson.dumps(deviceData))

      # non-blocking check for messages
      client.subscribe(b"iot-2/cmd/update-tracker/fmt/json")
      # Topics for IBM managed device notifications
      client.subscribe(b"iotdm-1/response")
      client.subscribe(b"iotdm-1/device/update")

      client.wait_msg()
      client.disconnect()
      time.sleep(0.01)
      
      # send notification if button was pressed since last time
      if pendingNotification == True:
        print('connecting to MQTT broker...')
        client.connect()
        client.publish(b"iot-2/evt/habit/fmt/json", ujson.dumps(payload))
        pendingNotification = False
        print('disconnecting from MQTT broker')
        client.disconnect()
        sleepDevice()
    

    # detect button presses
    firstButtonReading = button.value()
    time.sleep(0.01)
    secondButtonReading = button.value()
    if firstButtonReading and not secondButtonReading:
      buttonPressStarted = utime.ticks_ms()
    elif not firstButtonReading and secondButtonReading:
      duration = utime.ticks_diff(utime.ticks_ms(), buttonPressStarted)
      payload['energy'] = duration
      # notification will be sent
      pendingNotification = True
      beHappy()