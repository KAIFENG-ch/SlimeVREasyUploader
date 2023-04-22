/*
  NTP-TZ-DST (v2)
  NetWork Time Protocol - Time Zone - Daylight Saving Time

  This example shows:
  - how to read and set time
  - how to set timezone per country/city
  - how is local time automatically handled per official timezone definitions
  - how to change internal sntp start and update delay
  - how to use callbacks when time is updated

  This example code is in the public domain.
*/


#ifndef STASSID
#define STASSID "your-ssid"
#define STAPSK  "your-password"
#endif

// initial time (possibly given by an external RTC)
#define RTC_UTC_TEST 1510592825 // 1510592825 = Monday 13 November 2017 17:07:05 UTC


// This database is autogenerated from IANA timezone database
//    https://www.iana.org/time-zones
// and can be updated on demand in this repository
#include <TZ.h>

// "TZ_" macros follow DST change across seasons without source code change
// check for your nearest city in TZ.h

// espressif headquarter TZ
//#define MYTZ TZ_Asia_Shanghai

// example for "Not Only Whole Hours" timezones:
// Kolkata/Calcutta is shifted by 30mn
//#define MYTZ TZ_Asia_Kolkata

// example of a timezone with a variable Daylight-Saving-Time:
// demo: watch automatic time adjustment on Summer/Winter change (DST)
#define MYTZ TZ_Europe_London

////////////////////////////////////////////////////////

#include <ESP8266WiFi.h>
#include <coredecls.h>                  // settimeofday_cb()
#include <Schedule.h>
#include <PolledTimeout.h>

#include <time.h>                       // time() ctime()
#include <sys/time.h>                   // struct timeval

#include <sntp.h>                       // sntp_servermode_dhcp()

// for testing purpose:
extern "C" int clock_gettime(clockid_t unused, struct timespec *tp);

////////////////////////////////////////////////////////

static timeval tv;
static timespec tp;
static time_t now;
static uint32_t now_ms, now_us;

static esp8266::polledTimeout::periodicMs showTimeNow(60000);
static int time_machine_days = 0; // 0 = present
static bool time_machine_running = false;
static bool time_machine_run_once = false;

// OPTIONAL: change SNTP startup delay
// a weak function is already defined and returns 0 (RFC violation)
// it can be redefined:
//uint32_t sntp_startup_delay_MS_rfc_not_less_than_60000 ()
//{
//    //info_sntp_startup_delay_MS_rfc_not_less_than_60000_has_been_called = true;
//    return 60000; // 60s (or lwIP's original default: (random() % 5000))
//}

// OPTIONAL: change SNTP update delay
// a weak function is already defined and returns 1 hour
// it can be redefined:
//uint32_t sntp_update_delay_MS_rfc_not_less_than_15000 ()
//{
//    //info_sntp_update_delay_MS_rfc_not_less_than_15000_has_been_called = true;
//    return 15000; // 15s
//}

#define PTM(w) \
  Serial.print(" " #w "="); \
  Serial.print(tm->tm_##w);

void printTm(const char* what, const tm* tm) {
  Serial.print(what);
  PTM(isdst); PTM(yday); PTM(wday);
  PTM(year);  PTM(mon);  PTM(mday);
  PTM(hour);  PTM(min);  PTM(sec);
}

void showTime() {
  gettimeofday(&tv, nullptr);
  clock_gettime(0, &tp);
  now = time(nullptr);
  now_ms = millis();
  now_us = micros();

  Serial.println();
  printTm("localtime:", localtime(&now));
  Serial.println();
  printTm("gmtime:   ", gmtime(&now));
  Serial.println();

  // time from boot
  Serial.print("clock:     ");
  Serial.print((uint32_t)tp.tv_sec);
  Serial.print("s + ");
  Serial.print((uint32_t)tp.tv_nsec);
  Serial.println("ns");

  // time from boot
  Serial.print("millis:    ");
  Serial.println(now_ms);
  Serial.print("micros:    ");
  Serial.println(now_us);

  // EPOCH+tz+dst
  Serial.print("gtod:      ");
  Serial.print((uint32_t)tv.tv_sec);
  Serial.print("s + ");
  Serial.print((uint32_t)tv.tv_usec);
  Serial.println("us");

  // EPOCH+tz+dst
  Serial.print("time:      ");
  Serial.println((uint32_t)now);

  // timezone and demo in the future
  Serial.printf("timezone:  %s\n", getenv("TZ") ? : "(none)");

  // human readable
  Serial.print("ctime:     ");
  Serial.print(ctime(&now));

  // lwIP v2 is able to list more details about the currently configured SNTP servers
  for (int i = 0; i < SNTP_MAX_SERVERS; i++) {
    IPAddress sntp = *sntp_getserver(i);
    const char* name = sntp_getservername(i);
    if (sntp.isSet()) {
      Serial.printf("sntp%d:     ", i);
      if (name) {
        Serial.printf("%s (%s) ", name, sntp.toString().c_str());
      } else {
        Serial.printf("%s ", sntp.toString().c_str());
      }
      Serial.printf("- IPv6: %s - Reachability: %o\n",
                    sntp.isV6() ? "Yes" : "No",
                    sntp_getreachability(i));
    }
  }

  Serial.println();

  // show subsecond synchronisation
  timeval prevtv;
  time_t prevtime = time(nullptr);
  gettimeofday(&prevtv, nullptr);

  while (true) {
    gettimeofday(&tv, nullptr);
    if (tv.tv_sec != prevtv.tv_sec) {
      Serial.printf("time(): %u   gettimeofday(): %u.%06u  seconds are unchanged\n",
                    (uint32_t)prevtime,
                    (uint32_t)prevtv.tv_sec, (uint32_t)prevtv.tv_usec);
      Serial.printf("time(): %u   gettimeofday(): %u.%06u  <-- seconds have changed\n",
                    (uint32_t)(prevtime = time(nullptr)),
                    (uint32_t)tv.tv_sec, (uint32_t)tv.tv_usec);
      break;
    }
    prevtv = tv;
    delay(50);
  }

  Serial.println();
}

void time_is_set(bool from_sntp /* <= this parameter is optional */) {
  // in CONT stack, unlike ISRs,
  // any function is allowed in this callback

  if (time_machine_days == 0) {
    if (time_machine_running) {
      time_machine_run_once = true;
      time_machine_running = false;
    } else {
      time_machine_running = from_sntp && !time_machine_run_once;
    }
    if (time_machine_running) {
      Serial.printf("\n-- \n-- Starting time machine demo to show libc's "
                    "automatic DST handling\n-- \n");
    }
  }

  Serial.print("settimeofday(");
  if (from_sntp) {
    Serial.print("SNTP");
  } else {
    Serial.print("USER");
  }
  Serial.print(")");

  // time machine demo
  if (time_machine_running) {
    now = time(nullptr);
    const tm* tm = localtime(&now);
    Serial.printf(": future=%3ddays: DST=%s - ",
                  time_machine_days,
                  tm->tm_isdst ? "true " : "false");
    Serial.print(ctime(&now));
    gettimeofday(&tv, nullptr);
    constexpr int days = 30;
    time_machine_days += days;
    if (time_machine_days > 360) {
      tv.tv_sec -= (time_machine_days - days) * 60 * 60 * 24;
      time_machine_days = 0;
    } else {
      tv.tv_sec += days * 60 * 60 * 24;
    }
    settimeofday(&tv, nullptr);
  } else {
    Serial.println();
  }
}

void setup() {
  WiFi.persistent(false);
  WiFi.mode(WIFI_OFF);

  Serial.begin(115200);
  Serial.println("\nStarting in 2secs...\n");
  delay(2000);

  // install callback - called when settimeofday is called (by SNTP or user)
  // once enabled (by DHCP), SNTP is updated every hour by default
  // ** optional boolean in callback function is true when triggered by SNTP **
  settimeofday_cb(time_is_set);

  // setup RTC time
  // it will be used until NTP server will send us real current time
  Serial.println("Manually setting some time from some RTC:");
  time_t rtc = RTC_UTC_TEST;
  timeval tv = { rtc, 0 };
  settimeofday(&tv, nullptr);

  // NTP servers may be overridden by your DHCP server for a more local one
  // (see below)

  // ----> Here is the ONLY ONE LINE needed in your sketch
  configTime(MYTZ, "pool.ntp.org");
  // <----
  // Replace MYTZ by a value from TZ.h (search for this file in your filesystem).

  // Former configTime is still valid, here is the call for 7 hours to the west
  // with an enabled 30mn DST
  //configTime(7 * 3600, 3600 / 2, "pool.ntp.org");

  // OPTIONAL: disable obtaining SNTP servers from DHCP
  //sntp_servermode_dhcp(0); // 0: disable obtaining SNTP servers from DHCP (enabled by default)

  // Give now a chance to the settimeofday callback,
  // because it is *always* deferred to the next yield()/loop()-call.
  yield();

  // start network
  WiFi.mode(WIFI_STA);
  WiFi.begin(STASSID, STAPSK);

  // don't wait for network, observe time changing
  // when NTP timestamp is received
  showTime();
}

void loop() {
  if (showTimeNow) {
    showTime();
  }
}
