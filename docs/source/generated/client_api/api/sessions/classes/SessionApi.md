[**plexa_client v0.0.0**](../../../README.md)

***

[plexa_client](../../../modules.md) / [api/sessions](../README.md) / SessionApi

# Class: SessionApi

Defined in: [src/api/sessions.ts:7](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/sessions.ts#L7)

## Constructors

### Constructor

> **new SessionApi**(`http`): `SessionApi`

Defined in: [src/api/sessions.ts:9](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/sessions.ts#L9)

#### Parameters

##### http

[`HttpClient`](../../http/classes/HttpClient.md)

#### Returns

`SessionApi`

## Methods

### closeSession()

> **closeSession**(): `Promise`\<`unknown`\>

Defined in: [src/api/sessions.ts:53](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/sessions.ts#L53)

#### Returns

`Promise`\<`unknown`\>

***

### createSession()

> **createSession**(`courseId?`, `lessonId`, `lessonVersion`): `Promise`\<\{ `session`: [`Session`](../../interfaces/interfaces/Session.md); \}\>

Defined in: [src/api/sessions.ts:11](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/sessions.ts#L11)

#### Parameters

##### courseId?

`string` = `...`

##### lessonId

`string`

##### lessonVersion

`string`

#### Returns

`Promise`\<\{ `session`: [`Session`](../../interfaces/interfaces/Session.md); \}\>

***

### sendMessage()

> **sendMessage**(`content`, `sessionId?`): `Promise`\<\{ `assistant_message`: [`Message`](../../interfaces/interfaces/Message.md); `session`: [`Session`](../../interfaces/interfaces/Session.md); \}\>

Defined in: [src/api/sessions.ts:31](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/sessions.ts#L31)

#### Parameters

##### content

`string`

##### sessionId?

`string` | `null`

#### Returns

`Promise`\<\{ `assistant_message`: [`Message`](../../interfaces/interfaces/Message.md); `session`: [`Session`](../../interfaces/interfaces/Session.md); \}\>
