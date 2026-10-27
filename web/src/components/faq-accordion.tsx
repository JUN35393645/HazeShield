const questions = [
  {
    question: "When do I get paid?",
    answer: "In this prototype, a simulated payout is triggered if the API reading in your selected zone stays above 150 for two consecutive days. The prototype does not make real payments.",
  },
  {
    question: "What is the API?",
    answer: "API is Malaysia’s Air Pollutant Index, a measure used to describe air quality. HazeShield’s prototype uses an API threshold of above 150 on two consecutive days as its example trigger.",
  },
  {
    question: "Who can join?",
    answer: "HazeShield is designed for Malaysian outdoor and gig workers, including delivery riders, e-hailing drivers, food vendors, market traders, and other outdoor workers.",
  },
  {
    question: "How much does it cost?",
    answer: "The website shows prototype plan prices for demonstration only. They are simulated, and no premium is collected through this prototype.",
  },
  {
    question: "Is this real insurance?",
    answer: "No. HazeShield is a prototype for educational purposes. Payouts are simulated, and this is not an insurance offer or a substitute for insurance.",
  },
];

export function FaqAccordion() {
  return (
    <div className="faq-list">
      {questions.map(({ question, answer }) => (
        <details className="faq-item" key={question}>
          <summary>{question}</summary>
          <p>{answer}</p>
        </details>
      ))}
    </div>
  );
}
