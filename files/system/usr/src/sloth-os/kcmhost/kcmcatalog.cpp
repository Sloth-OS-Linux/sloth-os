#include "kcmcatalog.h"

#include <KPluginMetaData>
#include <QJsonArray>
#include <QJsonObject>

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
            QStringList keywords;
            const QString kw = md.value(QStringLiteral("X-KDE-Keywords"));
            if (!kw.isEmpty())
                keywords = kw.split(QLatin1Char(','), Qt::SkipEmptyParts);
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
    return out;
}
