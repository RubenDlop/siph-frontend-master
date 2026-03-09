import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-assistant',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './assistant.component.html',
  styleUrl: './assistant.component.scss',
})
export class AssistantComponent {
  readonly gradioUrl = 'http://127.0.0.1:7860';
  readonly safeUrl: SafeResourceUrl;

  readonly suggestions: string[] = [
    '¿Cómo creo una solicitud en SIPH?',
    '¿Qué estados tiene una solicitud?',
    '¿Cómo funciona la postulación de técnico?',
    '¿Qué documentos pide la verificación?',
    '¿Qué puede hacer el administrador?',
    '¿Qué hace la ruta /my-requests?',
  ];

  constructor(private sanitizer: DomSanitizer) {
    this.safeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(this.gradioUrl);
  }
}
