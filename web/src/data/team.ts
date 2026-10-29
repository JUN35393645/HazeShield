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
    photo: "/team/Jackson.jpeg",
  },
  {
    name: "Akhil Chiruvella",
    role: "Market Research Team",
    bio: "Explores worker needs and the market context for income protection.",
    photo: "/team/Akhil Chiruvella.jpeg",
  },
  {
    name: "Chen Hao",
    role: "CCO",
    bio: "Shapes customer communication and the way HazeShield is introduced.",
    photo: "/team/Chen Hao.jpeg",
  },
  {
    name: "Aqil",
    role: "CFO",
    bio: "Supports financial planning and the affordability of the concept.",
    photo: "/team/Aqil.jpeg",
  },
  {
    name: "Jehan",
    role: "CFO",
    bio: "Supports budgeting, financial tracking, and sustainable operations.",
    photo: "/team/Jehan.jpeg",
  },
  {
    name: "Ali",
    role: "CTO",
    bio: "Leads technical planning for the HazeShield prototype.",
    photo: "/team/Ali.jpeg",
  },
  {
    name: "Yu Jun",
    role: "CTO",
    bio: "Builds and develops the technology behind the prototype.",
    photo: "/team/Yu Jun.jpeg",
  },
];
