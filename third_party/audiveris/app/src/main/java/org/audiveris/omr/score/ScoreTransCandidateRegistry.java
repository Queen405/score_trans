package org.audiveris.omr.score;

import org.audiveris.omr.glyph.Glyph;
import org.audiveris.omr.glyph.Shape;
import org.audiveris.omr.sheet.Sheet;

import java.awt.Rectangle;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/** Recognition-time notehead template scores for the Score Trans sidecar. */
public final class ScoreTransCandidateRegistry
{
    public static final String SCORE_KIND = "audiveris_notehead_template";

    private static final Map<Sheet, List<LocationScores>> LOCATIONS = new WeakHashMap<>();

    private ScoreTransCandidateRegistry ()
    {
    }

    public static synchronized void beginSheet (Sheet sheet)
    {
        LOCATIONS.remove(sheet);
        sheet.setScoreTransNoteCandidateLocations(List.of());
        for (Glyph glyph : sheet.getGlyphIndex().getEntities()) {
            glyph.setScoreTransNoteCandidates(null);
        }
    }

    /** Record native template scores at a scanned location. */
    public static synchronized void record (Sheet sheet,
                                            int x,
                                            int y,
                                            Map<Shape, Double> scores)
    {
        if (scores.isEmpty()) return;

        final List<LocationScores> locations = LOCATIONS.computeIfAbsent(
                sheet, ignored -> new ArrayList<>());
        final int radius = Math.max(2, sheet.getInterline() / 2);
        LocationScores closest = null;
        double closestDistance = (double) radius * radius;
        for (LocationScores location : locations) {
            final double distance = squared(x, y, location.x(), location.y());
            if (distance <= closestDistance) {
                closest = location;
                closestDistance = distance;
            }
        }
        if (closest == null) {
            final EnumMap<Shape, Double> copy = new EnumMap<>(Shape.class);
            scores.forEach((shape, score) -> copy.merge(shape, normalize(score), Math::max));
            locations.add(new LocationScores(x, y, copy));
        } else {
            final LocationScores target = closest;
            scores.forEach((shape, score) ->
                    target.scores().merge(shape, normalize(score), Math::max));
        }
    }

    public static void recordForGlyph (Glyph glyph, Map<Shape, Double> scores)
    {
        if (glyph != null && !scores.isEmpty()) mergeOnGlyph(glyph, scores);
    }

    /** Persist the nearest match data on a recognized note's glyph before OMR save/reload. */
    public static synchronized void persistNear (Sheet sheet,
                                                 Rectangle bounds,
                                                 Glyph glyph,
                                                 int radius)
    {
        if (glyph == null) return;
        final List<Candidate> candidates = candidatesNear(sheet, bounds, radius);
        if (candidates.isEmpty()) return;
        final Map<Shape, Double> scores = new EnumMap<>(Shape.class);
        for (Candidate candidate : candidates) {
            try {
                scores.put(Shape.valueOf(candidate.shape()), candidate.score());
            } catch (IllegalArgumentException ignored) {
                // Ignore shapes unknown to this Audiveris build.
            }
        }
        mergeOnGlyph(glyph, scores);
    }

    public static synchronized List<Candidate> candidatesNear (Sheet sheet,
                                                               Rectangle bounds,
                                                               int radius)
    {
        final List<LocationScores> locations = LOCATIONS.get(sheet);
        return findCandidatesNear(locations, bounds, radius);
    }

    public static List<Candidate> candidatesNear (List<String> encodedLocations,
                                                  Rectangle bounds,
                                                  int radius)
    {
        if (encodedLocations == null || encodedLocations.isEmpty() || bounds == null) {
            return List.of();
        }
        final List<LocationScores> locations = new ArrayList<>();
        for (String encoded : encodedLocations) {
            final LocationScores location = decodeLocation(encoded);
            if (location != null) locations.add(location);
        }
        return findCandidatesNear(locations, bounds, radius);
    }

    public static synchronized void flush (Sheet sheet)
    {
        final List<LocationScores> locations = LOCATIONS.get(sheet);
        if (locations != null && !locations.isEmpty()) {
            final List<String> encoded = new ArrayList<>(
                    sheet.getScoreTransNoteCandidateLocations());
            encoded.addAll(locations.stream()
                    .map(ScoreTransCandidateRegistry::encodeLocation)
                    .toList());
            sheet.setScoreTransNoteCandidateLocations(encoded);
        }
        LOCATIONS.remove(sheet);
    }

    private static List<Candidate> findCandidatesNear (List<LocationScores> locations,
                                                       Rectangle bounds,
                                                       int radius)
    {
        if (locations == null || locations.isEmpty() || bounds == null) return List.of();

        final double cx = bounds.getCenterX();
        final double cy = bounds.getCenterY();
        LocationScores nearest = null;
        double nearestDistance = Double.MAX_VALUE;
        for (LocationScores location : locations) {
            final double distance = squared(cx, cy, location.x(), location.y());
            if (distance < nearestDistance) {
                nearest = location;
                nearestDistance = distance;
            }
        }
        if (nearest == null || nearestDistance > (double) radius * radius) return List.of();

        final Map<Shape, Double> bestByShape = new EnumMap<>(Shape.class);
        final int mergeRadius = Math.max(1, radius / 3);
        for (LocationScores location : locations) {
            if (squared(nearest.x(), nearest.y(), location.x(), location.y())
                    <= (double) mergeRadius * mergeRadius) {
                location.scores().forEach((shape, score) ->
                        bestByShape.merge(shape, score, Math::max));
            }
        }

        return bestByShape.entrySet().stream()
                .sorted(Map.Entry.<Shape, Double>comparingByValue(Comparator.reverseOrder()))
                .limit(5)
                .map(entry -> new Candidate(entry.getKey().toString(), entry.getValue()))
                .toList();
    }

    private static String encodeLocation (LocationScores location)
    {
        return location.x() + "," + location.y() + "|" + encode(location.scores());
    }

    private static LocationScores decodeLocation (String encoded)
    {
        if (encoded == null) return null;
        final int separator = encoded.indexOf('|');
        final int comma = encoded.indexOf(',');
        if (comma <= 0 || separator <= comma) return null;
        try {
            final int x = Integer.parseInt(encoded.substring(0, comma));
            final int y = Integer.parseInt(encoded.substring(comma + 1, separator));
            return new LocationScores(x, y, decode(encoded.substring(separator + 1)));
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    public static List<Candidate> candidatesFor (Glyph glyph)
    {
        if (glyph == null) return List.of();
        final Map<Shape, Double> scores = decode(glyph.getScoreTransNoteCandidates());
        return scores.entrySet().stream()
                .sorted(Map.Entry.<Shape, Double>comparingByValue(Comparator.reverseOrder()))
                .limit(5)
                .map(entry -> new Candidate(entry.getKey().toString(), entry.getValue()))
                .toList();
    }

    private static synchronized void mergeOnGlyph (Glyph glyph, Map<Shape, Double> additions)
    {
        final Map<Shape, Double> scores = decode(glyph.getScoreTransNoteCandidates());
        additions.forEach((shape, score) -> scores.merge(shape, normalize(score), Math::max));
        glyph.setScoreTransNoteCandidates(encode(scores));
    }

    private static double normalize (double score)
    {
        if (!Double.isFinite(score)) return 0;
        return Math.max(0, Math.min(1, score));
    }

    private static Map<Shape, Double> decode (String encoded)
    {
        final Map<Shape, Double> scores = new EnumMap<>(Shape.class);
        if (encoded == null || encoded.isBlank()) return scores;
        for (String item : encoded.split(";")) {
            final int separator = item.lastIndexOf(':');
            if (separator <= 0) continue;
            try {
                final Shape shape = Shape.valueOf(item.substring(0, separator));
                final double score = Double.parseDouble(item.substring(separator + 1));
                if (Double.isFinite(score)) scores.merge(shape, score, Math::max);
            } catch (IllegalArgumentException ignored) {
                // Ignore unknown or malformed metadata from a future Audiveris version.
            }
        }
        return scores;
    }

    private static String encode (Map<Shape, Double> scores)
    {
        final StringBuilder value = new StringBuilder();
        scores.entrySet().stream()
                .sorted(Map.Entry.<Shape, Double>comparingByValue(Comparator.reverseOrder()))
                .limit(5)
                .forEach(entry -> {
                    if (!value.isEmpty()) value.append(';');
                    value.append(entry.getKey()).append(':')
                            .append(String.format(java.util.Locale.ROOT, "%.6f", entry.getValue()));
                });
        return value.toString();
    }

    private static double squared (double x1,
                                   double y1,
                                   double x2,
                                   double y2)
    {
        final double dx = x1 - x2;
        final double dy = y1 - y2;
        return (dx * dx) + (dy * dy);
    }

    private record LocationScores(int x, int y, Map<Shape, Double> scores)
    {
    }

    public record Candidate(String shape, double score)
    {
    }
}
