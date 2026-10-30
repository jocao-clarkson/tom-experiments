FROM golang:1.22 AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /out/ ./cmd/...

FROM gcr.io/distroless/static-debian12
COPY --from=build /out/api /api
COPY --from=build /out/worker /worker
USER nonroot
ENTRYPOINT ["/api"]
