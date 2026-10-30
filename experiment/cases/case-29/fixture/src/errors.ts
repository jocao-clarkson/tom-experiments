export class CliError extends Error {
  constructor(message: string, public readonly exitCode: number) {
    super(message);
  }
}

/** Bad flags or arguments. Exit 2. */
export class UsageError extends CliError {
  constructor(message: string) {
    super(message, 2);
  }
}

/** The operation was not confirmed. Exit 1. */
export class AbortError extends CliError {
  constructor(message = "Aborted.") {
    super(message, 1);
  }
}

export class ApiError extends CliError {
  constructor(public readonly status: number, public readonly code: string, message: string) {
    super(message, 1);
  }
}
