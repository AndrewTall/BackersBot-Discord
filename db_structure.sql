--
-- Table structure for table "backers"
--

CREATE TABLE backers (
  "email" varchar(255) NOT NULL,
  "role_id" varchar(40) NOT NULL,
  "verification_code" varchar(40) DEFAULT NULL,
  "discord_user_id" varchar(40) DEFAULT NULL,
  CONSTRAINT "PK_backers_email" PRIMARY KEY ("email"),
  CONSTRAINT "UK_backers_email" UNIQUE ("email")
);

CREATE INDEX I_backers_email ON backers ("verification_code");
