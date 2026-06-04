/// <reference path="../.astro/types.d.ts" />

/// <reference types="astro/client" />

declare namespace App {
  interface Locals {
    auth?: {
      sub?: string;
      iss?: string;
      iat?: number;
    };
  }
}