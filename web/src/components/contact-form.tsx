"use client";

import { useState, type FormEvent } from "react";

export function ContactForm() {
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    setSubmitted(true);
    event.currentTarget.reset();
  }

  return (
    <form className="contact-form" onSubmit={handleSubmit} onChange={() => setSubmitted(false)}>
      <label htmlFor="contact-name">Name</label>
      <input id="contact-name" name="name" autoComplete="name" required minLength={2} maxLength={100} />
      <label htmlFor="contact-email">Email</label>
      <input id="contact-email" name="email" type="email" autoComplete="email" required maxLength={254} />
      <label htmlFor="contact-message">Message</label>
      <textarea id="contact-message" name="message" rows={5} required minLength={5} maxLength={2000} />
      <button className="button" type="submit">Send message</button>
      <p className="contact-success" role="status" aria-live="polite">
        {submitted ? "Thanks, we'll be in touch" : ""}
      </p>
    </form>
  );
}
