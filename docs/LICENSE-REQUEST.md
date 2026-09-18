# Demande de licence à l'auteur amont

> **Pour Florian** — à poster en *issue GitHub* sur
> <https://github.com/blacksole/Aion2-TM-DesktopApp> (ou sur le Discord du projet si l'auteur y est plus réactif).
> Sans fichier `LICENSE`, le dépôt est « tous droits réservés » par défaut : **on ne peut rien redistribuer** —
> ni fork public, ni binaire, ni paquet AUR/AppImage. C'est le blocage n°1 avant toute distribution Linux.

---

**Subject: Would you consider adding an OSI license?**

Hi blacksole,

Thanks for Aion2 TM — it's easily the most useful companion app for Aion 2, and I use it daily.

I've forked it to add Linux support (the app currently hard-depends on a few Windows-only APIs), plus an
installer and some build/packaging recommendations. I'd like to contribute all of that back upstream rather
than maintain a permanent fork, so the Linux port would land in your repo.

Before I can share anything publicly, there's a licensing question. The README says the project is "under a
custom license", but there's no `LICENSE` file in the repo. Without one, default copyright applies and nobody —
me included — can legally redistribute the code or a build of it.

Would you consider an OSI-approved license, ideally **MIT** or **Apache-2.0**? Either allows redistributing
binaries via installers, AUR packages or AppImages, and both are compatible with PySide6's LGPL licensing that
the app already links against.

Happy to open a PR whenever suits you. Thanks either way!
