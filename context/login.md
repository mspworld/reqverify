# Login

## Login page layout

The login page shows an email field, a password field, and a Sign In
button. Below the button is a "Forgot password?" link.

## Session behavior

A created session keeps the user signed in across page reloads until they
explicitly sign out or the session expires after 24 hours of inactivity.
The password used to sign in is discarded from memory immediately after
the session is created and is never written to logs.
