# Kippy Cloud API (new app) – Unofficial Documentation

> **Author:** [@IamDiesel](https://github.com/IamDiesel) > **Reverse engineered:** August 2026 (2026-08-08)
> **Reference implementation:** [`custom_components/kippy/api/`](custom_components/kippy/api/) in this repository
> **License:** MIT (same as this repository). If you build on this work, a credit/link back is appreciated.

This document describes the cloud API used by the **new Kippy app**, which replaced the legacy
`prod.kippyapi.eu/v2/*.php` API. Accounts created with or migrated to the new app **no longer work with
the legacy API**.

The new backend consists of:

- **Amazon Cognito** (user pool, region `eu-west-1`) for authentication
- **AWS AppSync** (GraphQL) for all data queries and commands

This is unofficial and not affiliated with or endorsed by Kippy. The API may change at any time.

---

## 1. Overview

| Item                  | Value                                                                            |
| --------------------- | -------------------------------------------------------------------------------- |
| Auth endpoint         | `https://cognito-idp.eu-west-1.amazonaws.com/`                                   |
| Cognito App Client ID | `57bn1c33eu2r5libvqvhfnv4qb` (public client of the mobile app, no secret)        |
| GraphQL endpoint      | `https://l2nea6uaizdn3j3h2ex7frcqhy.appsync-api.eu-west-1.amazonaws.com/graphql` |
| GraphQL auth          | `Authorization: Bearer <IdToken>` (Cognito **IdToken**, not the AccessToken)     |
| Request body          | `{"query": "...", "variables": {...}}`                                           |

### Parsing note

AWS responses sometimes carry a missing or unexpected `Content-Type` (Cognito uses
`application/x-amz-json-1.1`). Disable strict content-type checks when decoding JSON,
e.g. `await resp.json(content_type=None)` in aiohttp.

---

## 2. Authentication (Cognito)

### 2.1 Login – `InitiateAuth` / `USER_PASSWORD_AUTH`

```http
POST https://cognito-idp.eu-west-1.amazonaws.com/
X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth
Content-Type: application/x-amz-json-1.1
X-Amz-User-Agent: aws-amplify/0.0.x dart
```

```json
{
  "AuthFlow": "USER_PASSWORD_AUTH",
  "ClientId": "57bn1c33eu2r5libvqvhfnv4qb",
  "AuthParameters": {
    "USERNAME": "user@example.com",
    "PASSWORD": "my_secure_password"
  }
}
```

Response (excerpt):

```json
{
  "AuthenticationResult": {
    "IdToken": "eyJra...",
    "AccessToken": "eyJra...",
    "RefreshToken": "eyJjd...",
    "ExpiresIn": 3600,
    "TokenType": "Bearer"
  }
}
```

A response without `AuthenticationResult` means the login failed (or Cognito requires a challenge).

### 2.2 Token expiry

When the IdToken has expired, AppSync answers with **HTTP 401**. The reference implementation simply
logs in again with the stored credentials and retries the request once.

Not yet implemented, but the standard Cognito way would be a refresh without the password:

```json
{
  "AuthFlow": "REFRESH_TOKEN_AUTH",
  "ClientId": "57bn1c33eu2r5libvqvhfnv4qb",
  "AuthParameters": { "REFRESH_TOKEN": "<RefreshToken>" }
}
```

---

## 3. GraphQL operations

All operations are `POST` requests to the GraphQL endpoint:

```http
POST https://l2nea6uaizdn3j3h2ex7frcqhy.appsync-api.eu-west-1.amazonaws.com/graphql
Authorization: Bearer <IdToken>
Content-Type: application/json
```

GraphQL-level errors are returned with HTTP 200 and an `errors` array next to `data`.

### Response envelope

Every operation (query and mutation) returns an envelope object with the same status fields,
which the app always requests:

```graphql
code             # "200" on success (a String, not an Int)
translationCode  # i18n key of the message, usually null
message          # e.g. "Ok"
```

Queries additionally carry their payload (`pets`, `products`, `petlinkGps`, ...) next to these fields.
The app also requests `__typename` on every object (Amplify default); this is optional.

### Timestamps

Dates are ISO 8601 strings. Some are returned with nanosecond precision and an explicit offset, e.g.
`2026-08-11T23:33:12.111323758+00:00`. Python's `datetime.fromisoformat` only accepts up to 6
fractional digits, so truncate before parsing.

### API key (unauthenticated operations)

A few public operations (e.g. `getCountryState`) are called by the app **without** a Cognito token,
using the AppSync API key embedded in the app instead:

```http
x-api-key: da2-4hvojsuvavchnpfqyzoeptdv5a
```

AppSync API keys expire and get rotated, so this value may stop working.

### Identifiers

| Name                                         | Meaning                     | Source                        |
| -------------------------------------------- | --------------------------- | ----------------------------- |
| `petId`                                      | ID of the pet               | `getPets → pets[].id`         |
| device ID (`id` / `deviceId` / `productIds`) | ID of the tracker (product) | `getProducts → products[].id` |

IDs are strings; always send them as `String`.

---

### 3.1 `getPets` – list pets

```graphql
query getPets {
  getPets {
    pets {
      id
      name
      species
      image {
        url
      }
    }
  }
}
```

Variables: none.

```json
{
  "data": {
    "getPets": {
      "pets": [
        {
          "id": "12345",
          "name": "Lola",
          "species": "CAT",
          "image": { "url": "https://..." }
        }
      ]
    }
  }
}
```

`species`: `CAT`, `DOG` (others possible).

---

### 3.2 `getProducts` – trackers of a pet

```graphql
query getProducts($petId: String!) {
  getProducts(petId: $petId) {
    products {
      id
      entityType
      serialNumber
      deviceType
      subscriptionIsActive
      lastKnownStatus {
        energySavingMode
        firmwareVersion
      }
    }
  }
}
```

Variables: `{"petId": "12345"}`

```json
{
  "data": {
    "getProducts": {
      "products": [
        {
          "id": "67890",
          "entityType": "PETLINK_GPS",
          "serialNumber": "KPY123456",
          "deviceType": "CAT",
          "subscriptionIsActive": true,
          "lastKnownStatus": {
            "energySavingMode": "OFF",
            "firmwareVersion": "2.1.0"
          }
        }
      ]
    }
  }
}
```

`entityType` observed: `PETLINK_GPS`. The reference implementation also accepts `KIPPY_GPS`, `EVO_GPS`
and `TRACKER` as GPS trackers (unverified).

---

### 3.3 `getPetlinkGps` – position, status and settings of a tracker

All fields below can be combined in one query; the reference implementation queries them in two
separate calls (settings during setup, position/status on every poll).

```graphql
query getPetlinkGps($id: String!) {
  getPetlinkGps(id: $id) {
    petlinkGps {
      lastKnownPosition {
        lat
        lng
        alt
        radius
        positionType
        date
      }
      lastKnownStatus {
        battery
        liveTracking
        energySavingMode
        date
      }
      settings {
        updateFrequency
        enableGpsOnDefault
      }
    }
  }
}
```

Variables: `{"id": "67890"}` (device ID)

```json
{
  "data": {
    "getPetlinkGps": {
      "petlinkGps": {
        "lastKnownPosition": {
          "lat": 51.0,
          "lng": 10.0,
          "alt": 245.0,
          "radius": 15,
          "positionType": "GPS",
          "date": "2026-08-09T11:45:00.000Z"
        },
        "lastKnownStatus": {
          "battery": 85,
          "liveTracking": "OFF",
          "energySavingMode": "OFF",
          "date": "2026-08-09T11:45:00.000Z"
        },
        "settings": { "updateFrequency": 15, "enableGpsOnDefault": true }
      }
    }
  }
}
```

| Field                    | Notes                                                               |
| ------------------------ | ------------------------------------------------------------------- |
| `radius`                 | Accuracy in metres                                                  |
| `positionType`           | `GPS`, `WIFI`, `LBS` (cell based, low accuracy)                     |
| `lastKnownPosition.date` | Time of the position fix (ISO 8601, may have > 6 fractional digits) |
| `lastKnownStatus.date`   | Last contact with the tracker                                       |
| `battery`                | Percent                                                             |
| `liveTracking`           | `OFF`, `REQUESTED` (command sent, tracker not yet live), `ON`       |
| `energySavingMode`       | `ON` / `OFF`                                                        |
| `updateFrequency`        | Update interval in **minutes**                                      |

#### Full field set (as requested by the app)

The app itself requests considerably more fields. Values in comments are observed examples.

```graphql
query getPetlinkGps($id: String!) {
  getPetlinkGps(id: $id) {
    code
    translationCode
    message
    petlinkGps {
      id
      entityType # "PETLINK_GPS"
      serialNumber
      petId
      userId
      creationDate
      updateDate
      countryCode # "DE"
      timezone
      lastKnownPosition {
        lat
        lng
        alt
        radius # metres
        precision # "HIGH", ...
        speed
        positionType # GPS | WIFI | LBS
        date
        isSkip
      }
      lastKnownStatus {
        battery # percent
        charging
        flashlight # "ON" / "OFF"
        sound # "ON" / "OFF"
        liveTracking # OFF | REQUESTED | ON
        geofence # "ON" / "OFF"
        inGeofence
        energySavingMode # "ON" / "OFF"
        inEnergySavingZone # bool
        tourRecording # "ON" / "OFF"
        firmwareVersion # "11.1.70"
        offline # bool
        shutdown # bool
        date
      }
      geofenceCoordinates {
        lat
        lng
      }
      newFirmwareVersion {
        url
        version
      } # null when no update is available
      settings {
        activityProfile # "MODERATELY_ACTIVE", ...
        updateFrequency # minutes
        enableGpsOnDefault
        optimizationDone
        sentinelMigrationDone
        lastOptimizationAttempt
        migrationWaitingForConnection
      }
      subscriptionId
      subscriptionIsActive
      logEnabled
      endOfLifeDevice
    }
  }
}
```

Useful for Home Assistant: `charging`, `offline`, `shutdown`, `inEnergySavingZone`, `inGeofence`,
`speed`, `precision` and `newFirmwareVersion` (firmware update available).

---

### 3.4 `getActivitiesCat` – weekly activity report (cats)

```graphql
query getActivitiesCat(
  $petId: String!
  $weekIndex: Int!
  $from: Int!
  $to: Int!
) {
  getActivitiesCat(petId: $petId, weekIndex: $weekIndex, from: $from, to: $to) {
    activityReport {
      walk {
        value
      }
      sleep {
        value
      }
      calories {
        value
      }
      steps {
        value
      }
      feed {
        value
      }
      jumps {
        value
      }
      onTheMove {
        value
      }
      highMovement {
        value
      }
      grooming {
        value
      }
    }
  }
}
```

| Variable    | Type   | Meaning                                          |
| ----------- | ------ | ------------------------------------------------ |
| `petId`     | String | Pet ID                                           |
| `weekIndex` | Int    | ISO year + ISO week as `YYYYWW`, e.g. `202632`   |
| `from`      | Int    | Unix timestamp (s), Monday 00:00:00 of that week |
| `to`        | Int    | Unix timestamp (s), Sunday 23:59:59 of that week |

The API expects exactly the boundaries of the week given in `weekIndex`.

---

### 3.5 `getPositionsHistory` – GPS history

```graphql
query getPositionsHistory($petId: String!, $from: String, $to: String) {
  getPositionsHistory(petId: $petId, from: $from, to: $to) {
    positions {
      lat
      lng
      radius
      precision
      positionType
      date
      isSkip
    }
  }
}
```

Variables:

```json
{
  "petId": "12345",
  "from": "2026-08-08T00:00:00.000Z",
  "to": "2026-08-08T23:59:59.999Z"
}
```

---

### 3.6 `sendSetting` – change tracker settings

```graphql
mutation sendSetting($setting: Setting!) {
  sendSetting(setting: $setting) {
    code
    message
  }
}
```

**Update interval / GPS on default** – `updateObject` is a _stringified_ JSON object:

```json
{
  "setting": {
    "operationType": "UPDATE",
    "settingType": "UPDATE_FREQUENCY",
    "deviceId": "67890",
    "updateObject": "{\"updateFrequency\": 15, \"enableGpsOnDefault\": true}"
  }
}
```

**Energy saving mode** – `ACTIVATE` or `DEACTIVATE`:

```json
{
  "setting": {
    "operationType": "ACTIVATE",
    "settingType": "ENERGY_SAVING_ZONE",
    "deviceId": "67890",
    "modeType": "SENTINEL"
  }
}
```

---

### 3.7 `sendCommand` – commands to the tracker

```graphql
mutation sendCommand($command: Command!) {
  sendCommand(command: $command) {
    code
    message
  }
}
```

| Action                    | Variables                                                                                             |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| Start live tracking       | `{"command": {"commandType": "LIVE_TRACKING", "id": "67890", "modeType": "SENTINEL"}}`                |
| Stop live tracking        | `{"command": {"commandType": "LIVE_TRACKING", "id": "67890", "duration": 0, "modeType": "SENTINEL"}}` |
| Request a position update | `{"command": {"commandType": "WAKEUP", "id": "67890", "modeType": "SENTINEL"}}`                       |

After a command, query `getPetlinkGps` again to read the new state. After starting live tracking,
`liveTracking` is `REQUESTED` until the tracker reports `ON`.

---

### 3.8 `appKeepAlive` – keep live tracking running

```graphql
mutation appKeepAlive($productIds: [String!]!) {
  appKeepAlive(productIds: $productIds) {
    code
    message
  }
}
```

Variables: `{"productIds": ["67890"]}`

While live tracking is active (`ON` or `REQUESTED`), this mutation has to be sent repeatedly.
Otherwise the tracker falls back to its normal mode.

**Observed app behaviour:** while the live map is open, the app sends `appKeepAlive` **every 20 seconds**
(measured over 15 consecutive calls, 19.7–20.3 s apart).

The reference implementation currently sends it once right after starting live tracking and then on every
poll cycle, so the poll interval during live tracking should be ≤ 20 s.

---

### 3.9 `getGeofences` – virtual fences (read)

Returns all geofences of the account. A geofence is a **polygon** (list of coordinates), not a circle.

```graphql
query getGeofences {
  getGeofences {
    code
    message
    translationCode
    geofences {
      id
      entityType # "GEOFENCE"
      creationDate
      updateDate
      userId
      name
      position {
        # polygon vertices
        lat
        lng
      }
      devices # device IDs the fence is assigned to (observed: null)
    }
  }
}
```

Variables: none.

```json
{
  "data": {
    "getGeofences": {
      "code": "200",
      "message": "Ok",
      "translationCode": null,
      "geofences": [
        {
          "id": "<uuid>",
          "entityType": "GEOFENCE",
          "name": "Garden",
          "creationDate": "2026-03-30T14:05:29.654Z",
          "updateDate": "2026-03-30T14:05:29.654Z",
          "userId": "<uuid>",
          "position": [
            { "lat": 51.0, "lng": 10.0 },
            { "lat": 51.001, "lng": 10.0 },
            { "lat": 51.001, "lng": 10.0015 },
            { "lat": 51.0, "lng": 10.0015 }
          ],
          "devices": null
        }
      ]
    }
  }
}
```

The geofence status of a tracker is visible in `getPetlinkGps` (`lastKnownStatus.geofence`,
`lastKnownStatus.inGeofence`, `geofenceCoordinates`).

---

### 3.10 `getPetHistory` – event timeline / notifications

Returns the pet's event history (the notification feed of the app). The app calls it without variables,
which returns events for all pets.

```graphql
query getPetHistory($petId: String) {
  getPetHistory(petId: $petId) {
    code
    translationCode
    message
    petHistory {
      id
      entityType # "PET_HISTORY_EVENT"
      creationDate
      eventType
      petId
      date
      extra {
        address
        contentMessage {
          position {
            lat
            lng
          }
          name
          contact
          message
          petName
        }
        serialNumber
        newSerialNumber
        brazeNotification {
          title
          body
        }
        currentTermEndDate
      }
      read # bool, read in the app
    }
  }
}
```

Observed `eventType` values (135 events, Feb–Aug 2026):

| eventType                | Meaning                                                  | `extra`                           |
| ------------------------ | -------------------------------------------------------- | --------------------------------- |
| `ENERGY_SAVING_ZONE_IN`  | Tracker entered the energy saving zone (e.g. home Wi-Fi) | –                                 |
| `ENERGY_SAVING_ZONE_OUT` | Tracker left the energy saving zone                      | –                                 |
| `DEVICE_BATTERY`         | Battery notification                                     | –                                 |
| `DEVICE_BATTERY_20`      | Battery at 20 %                                          | –                                 |
| `DEVICE_BATTERY_10`      | Battery at 10 %                                          | –                                 |
| `DEVICE_POSITION`        | Position event                                           | `address` (reverse geocoded)      |
| `FIRMWARE_UPDATE`        | Firmware was updated                                     | –                                 |
| `REPLACEMENT`            | Tracker replaced                                         | `serialNumber`, `newSerialNumber` |

Most events come with `extra: null`. The history is a good source for Home Assistant events, e.g.
"cat left home" (`ENERGY_SAVING_ZONE_OUT`).

---

### 3.11 `getCountryState` – country list (public, API key)

Called with the **API key** instead of a Bearer token (see section 3, _API key_). Returns the list of
countries including the radio configuration the tracker uses for GPS optimization.

```graphql
query getCountryState($languageId: LanguageId, $countryId: String) {
  getCountryState(languageId: $languageId, countryId: $countryId) {
    code
    translationCode
    message
    items {
      code # ISO country code, e.g. "DE"
      name # localized name
      gpsOptimizationCommand {
        rfTecnology # sic (typo in the schema), e.g. "F1705TB"
        rfBand # e.g. "F1705B524421"
      }
    }
  }
}
```

Variables: `{"languageId": "EN"}` (196 countries returned). Not needed for a Home Assistant integration.

---

## 4. Typical flow

1. `InitiateAuth` → keep `IdToken` (and credentials or `RefreshToken`)
2. `getPets` → pet IDs
3. `getProducts(petId)` per pet → device IDs
4. Poll `getPetlinkGps(id)` per device
   - idle: optionally `sendCommand WAKEUP` for a fresh position
   - live tracking: `appKeepAlive` every 20 s
5. `getActivitiesCat` / `getPositionsHistory` as needed
6. On HTTP 401: re-authenticate and retry once

---

## 5. Not yet explored

- **Geofences** – reading works (`getGeofences`), create/update/delete/assign mutations not captured yet
- **Dog activities** – a dog-specific query (e.g. `getActivitiesDog`) probably exists but has not been verified
- **Firmware updates** – availability is visible via `getPetlinkGps → newFirmwareVersion`; no operation
  identified to trigger an update
- **Flashlight / sound** – status fields exist (`lastKnownStatus.flashlight`, `.sound`); the matching
  `sendCommand` command types have not been captured
- **Energy saving zones (Wi-Fi)** – zone enter/leave events exist (`getPetHistory`), but zone management
  operations are unknown
- **Push / realtime** – no AppSync subscriptions observed; the app polls
- **Full schema** – further fields on the types above very likely exist; AppSync introspection was not examined
