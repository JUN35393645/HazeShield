"use client";

import Image from "next/image";
import { useState } from "react";
import { team } from "@/data/team";

function initials(name: string) {
  return name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function TeamCard({ name, role, bio, photo, photoPosition, index }: (typeof team)[number] & { index: number }) {
  const [photoFailed, setPhotoFailed] = useState(false);

  return (
    <article className="team-card">
      <div className="team-photo">
        <div className="team-avatar">
          {photo && !photoFailed ? (
            <Image
              src={photo}
              alt={`${name}, ${role}`}
              fill
              sizes="150px"
              style={{ objectPosition: photoPosition }}
              onError={() => setPhotoFailed(true)}
            />
          ) : (
            <span className={`team-initials initials-${index % 4}`} aria-label={`${name} initials`}>
              {initials(name)}
            </span>
          )}
        </div>
      </div>
      <div className="team-card-copy">
        <h3>{name}</h3>
        <p className="team-role">{role}</p>
        <p>{bio}</p>
      </div>
    </article>
  );
}

export function TeamGrid() {
  return (
    <div className="team-grid">
      {team.map((member, index) => <TeamCard key={member.name} {...member} index={index} />)}
    </div>
  );
}
