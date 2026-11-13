#include "kcmcatalog.h"

#include <KPluginMetaData>
#include <QJsonArray>
#include <QJsonObject>
#include <QLocale>

KcmCatalog::KcmCatalog(QObject *parent)
    : QObject(parent)
{
}

static bool forDesktop(const KPluginMetaData &md)
{
    // the same rule as System Settings: no form factor given, or "desktop" among them
    const QStringList factors = md.formFactors();
    return factors.isEmpty() || factors.contains(QStringLiteral("desktop"));
}

QVariantList KcmCatalog::modules() const
{
    QVariantList out;
    const auto add = [&out](const QString &dir, bool widget) {
        const auto list = KPluginMetaData::findPlugins(dir);
        for (const KPluginMetaData &md : list) {
            if (!forDesktop(md))
                continue;
            const QJsonObject raw = md.rawData();
            // the search words in English and in the user's language (X-KDE-Keywords[hu], [pt_BR]…)
            QStringList keywords;
            const QString locale = QLocale().name();   // e.g. "hu_HU"
            for (const QString &key : {QStringLiteral("X-KDE-Keywords"),
                                       QStringLiteral("X-KDE-Keywords[%1]").arg(locale),
                                       QStringLiteral("X-KDE-Keywords[%1]").arg(locale.section(QLatin1Char('_'), 0, 0))}) {
                const QString kw = raw.value(key).toString();
                if (!kw.isEmpty())
                    keywords += kw.split(QLatin1Char(','), Qt::SkipEmptyParts);
            }
            out.append(QVariantMap{
                {QStringLiteral("id"), md.pluginId()},
                {QStringLiteral("name"), md.name()},
                {QStringLiteral("description"), md.description()},
                {QStringLiteral("icon"), md.iconName()},
                {QStringLiteral("category"), raw.value(QStringLiteral("X-KDE-System-Settings-Parent-Category")).toString()},
                {QStringLiteral("weight"), raw.value(QStringLiteral("X-KDE-Weight")).toVariant()},
                {QStringLiteral("keywords"), keywords},
                {QStringLiteral("widget"), widget},
            });
        }
    };
    add(QStringLiteral("plasma/kcms/systemsettings"), false);
    add(QStringLiteral("plasma/kcms/systemsettings_qwidgets"), true);
    add(QStringLiteral("plasma/kcms"), false);   // "About this System" (kcm_about-distro), shown by System Settings too
    return out;
}
