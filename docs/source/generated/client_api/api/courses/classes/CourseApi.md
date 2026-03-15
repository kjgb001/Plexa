[**plexa_client v0.0.0**](../../../README.md)

***

[plexa_client](../../../modules.md) / [api/courses](../README.md) / CourseApi

# Class: CourseApi

Defined in: [src/api/courses.ts:4](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/courses.ts#L4)

## Constructors

### Constructor

> **new CourseApi**(`http`): `CourseApi`

Defined in: [src/api/courses.ts:6](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/courses.ts#L6)

#### Parameters

##### http

[`HttpClient`](../../http/classes/HttpClient.md)

#### Returns

`CourseApi`

## Methods

### get()

> **get**(`courseId`): `Promise`\<[`Course`](../../interfaces/interfaces/Course.md)\>

Defined in: [src/api/courses.ts:12](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/courses.ts#L12)

#### Parameters

##### courseId

`string`

#### Returns

`Promise`\<[`Course`](../../interfaces/interfaces/Course.md)\>

***

### listDiscoverable()

> **listDiscoverable**(): `Promise`\<\{ `courses`: [`Course`](../../interfaces/interfaces/Course.md)[]; \}\>

Defined in: [src/api/courses.ts:8](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/courses.ts#L8)

#### Returns

`Promise`\<\{ `courses`: [`Course`](../../interfaces/interfaces/Course.md)[]; \}\>

***

### listLessons()

> **listLessons**(`courseId`): `Promise`\<\{ `lessons`: [`Lesson`](../../interfaces/interfaces/Lesson.md)[]; \}\>

Defined in: [src/api/courses.ts:22](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/courses.ts#L22)

#### Parameters

##### courseId

`string`

#### Returns

`Promise`\<\{ `lessons`: [`Lesson`](../../interfaces/interfaces/Lesson.md)[]; \}\>

***

### requestEnrollment()

> **requestEnrollment**(`courseId`): `Promise`\<`unknown`\>

Defined in: [src/api/courses.ts:16](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/courses.ts#L16)

#### Parameters

##### courseId

`string`

#### Returns

`Promise`\<`unknown`\>
