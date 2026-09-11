import { bootstrapApplication } from "@angular/platform-browser";
import { provideHttpClient, withInterceptors } from "@angular/common/http";
import { authInterceptor } from "./app/core/api";
import { provideRouter } from "@angular/router";
import { App } from "./app/app";
import { routes } from "./app/app.routes";
bootstrapApplication(App, {
  providers: [
    provideHttpClient(withInterceptors([authInterceptor])),
    provideRouter(routes),
  ],
}).catch(console.error);
