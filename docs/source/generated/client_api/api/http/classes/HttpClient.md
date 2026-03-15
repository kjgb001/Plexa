[**plexa_client v0.0.0**](../../../README.md)

***

[plexa_client](../../../modules.md) / [api/http](../README.md) / HttpClient

# Class: HttpClient

Defined in: [src/api/http.ts:9](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/http.ts#L9)

## Constructors

### Constructor

> **new HttpClient**(`getAuthHeaders`): `HttpClient`

Defined in: [src/api/http.ts:12](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/http.ts#L12)

#### Parameters

##### getAuthHeaders

() => `Promise`\<`Record`\<`string`, `string`\>\>

#### Returns

`HttpClient`

## Properties

### UNVERSIONED\_ENDPOINTS

> **UNVERSIONED\_ENDPOINTS**: `Set`\<`string`\>

Defined in: [src/api/http.ts:55](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/http.ts#L55)

## Methods

### request()

> **request**\<`T`\>(`path`, `options?`): `Promise`\<`T`\>

Defined in: [src/api/http.ts:16](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/http.ts#L16)

#### Type Parameters

##### T

`T`

#### Parameters

##### path

`string`

##### options?

`RequestInit` = `{}`

#### Returns

`Promise`\<`T`\>
