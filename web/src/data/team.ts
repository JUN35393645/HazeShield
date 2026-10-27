export type TeamMember = {
  name: string;
  role: string;
  bio: string;
  photo?: string;
};

export const team: TeamMember[] = [
  {
    name: "Jackson",
    role: "CEO",
    bio: "Guides the project’s direction and coordinates the team’s work.",
  },
  {
    name: "Akhil Chiruvella",
    role: "Market Research Team",
    bio: "Explores worker needs and the market context for income protection.",
  },
  {
    name: "Chen Hao",
    role: "CCO",
    bio: "Shapes customer communication and the way HazeShield is introduced.",
  },
  {
    name: "Aqil",
    role: "CFO",
    bio: "Supports financial planning and the affordability of the concept.",
  },
  {
    name: "Jehan",
    role: "CFO",
    bio: "Supports budgeting, financial tracking, and sustainable operations.",
  },
  {
    name: "Ali",
    role: "CTO",
    bio: "Leads technical planning for the HazeShield prototype.",
  },
  {
    name: "Yu Jun",
    role: "CTO",
    bio: "Builds and develops the technology behind the prototype.",
  },
];
