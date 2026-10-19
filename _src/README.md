# 항만 AI 화상회의 — 소스

- 배포: `meet/` (GitHub Pages, gh-pages 브랜치)
- 빌드: `npm i trystero@0.26.0 @trystero-p2p/mqtt@0.26.0 @trystero-p2p/torrent@0.26.0 esbuild` → `npx esbuild _src/app.js --bundle --format=esm --minify --target=es2020 --outfile=meet/app.js`
- 구조: WebRTC mesh(P2P). 신호 교환은 공용 Nostr 릴레이(또는 MQTT·BitTorrent), 회의 암호로 AES-GCM 암호화. 미디어·채팅·파일은 참여자 간 직접 DTLS-SRTP 암호화 전송.
