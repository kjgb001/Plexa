[**plexa_client v0.0.0**](../../../README.md)

***

[plexa_client](../../../modules.md) / [api/errors](../README.md) / ApiError

# Class: ApiError

Defined in: [src/api/errors.ts:1](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/errors.ts#L1)

## Extends

- `Error`

## Extended by

- [`NotFoundError`](NotFoundError.md)
- [`UnauthorizedError`](UnauthorizedError.md)
- [`ConflictError`](ConflictError.md)

## Constructors

### Constructor

> **new ApiError**(`status`, `detail?`): `ApiError`

Defined in: [src/api/errors.ts:5](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/errors.ts#L5)

#### Parameters

##### status

`number`

##### detail?

`string`

#### Returns

`ApiError`

#### Overrides

`Error.constructor`

## Properties

### cause?

> `optional` **cause**: `unknown`

Defined in: node\_modules/typescript/lib/lib.es2022.error.d.ts:26

#### Inherited from

`Error.cause`

***

### detail?

> `optional` **detail**: `string`

Defined in: [src/api/errors.ts:3](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/errors.ts#L3)

***

### message

> **message**: `string`

Defined in: node\_modules/typescript/lib/lib.es5.d.ts:1077

#### Inherited from

`Error.message`

***

### name

> **name**: `string`

Defined in: node\_modules/typescript/lib/lib.es5.d.ts:1076

#### Inherited from

`Error.name`

***

### stack?

> `optional` **stack**: `string`

Defined in: node\_modules/typescript/lib/lib.es5.d.ts:1078

#### Inherited from

`Error.stack`

***

### status

> **status**: `number`

Defined in: [src/api/errors.ts:2](https://github.com/kjgb001/Plexa/blob/ef825c87ddfab1b3ad678ff32fe58cc3c1525369/plexa_client/src/api/errors.ts#L2)
