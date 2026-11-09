/**
 * Application Configuration
 * 
 * Centralized configuration file for environment variables and app constants.
 */

export const config = {
  // Base URL for the application (defaults to localhost:3000 if not set)
  // To change this to 8000, update NEXT_PUBLIC_BASE_URL in your .env.local file
  baseUrl: process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000',
  
  // You can add more config variables here as your app grows
};
