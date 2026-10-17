/** Every error a command throws maps to a documented exit code. */
export class CliError extends Error {
  constructor(message: string, readonly exitCode: number) {
    super(message);
    this.name = new.target.name;
  }
}

/** Bad flags, missing arguments, or a prompt that cannot be answered. Exit 2. */
export class UsageError extends CliError {
  constructor(message: string) {
    super(message, 2);
  }
}

/** The API returned an error or could not be reached. Exit 4. */
export class ApiError extends CliError {
  constructor(message: string, readonly status?: number) {
    super(message, 4);
  }
}
